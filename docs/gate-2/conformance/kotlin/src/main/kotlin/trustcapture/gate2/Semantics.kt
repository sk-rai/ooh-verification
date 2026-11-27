package trustcapture.gate2

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive

private val decimalKeys = setOf("value", "scale", "unit")
private val asciiWhitespace = setOf(' ', '\t', '\n', '\u000B', '\u000C', '\r')

internal fun answerError(field: JsonObject, value: JsonElement?, required: Boolean): String? {
    if (value == null) return if (required) "ANSWER_REQUIRED" else null
    if (value.isJsonNull) return "ANSWER_NULL"
    return when (field.text("type")) {
        "boolean" -> if (value.boolean() == null) "ANSWER_TYPE" else null
        "text" -> {
            val text = value.string() ?: return "ANSWER_TYPE"
            if (text.all { it in asciiWhitespace }) "ANSWER_EMPTY" else null
        }
        "enum" -> {
            val id = value.string() ?: return "ANSWER_TYPE"
            if (field.array("options").none { it.asString == id }) "ANSWER_ENUM" else null
        }
        "decimal" -> decimalError(field, value)
        else -> error("Unvalidated field type")
    }
}

private fun decimalError(field: JsonObject, value: JsonElement): String? {
    val decimal = value.objectValue()?.takeIf { it.keySet() == decimalKeys } ?: return "ANSWER_TYPE"
    val text = decimal.get("value").string() ?: return "ANSWER_TYPE"
    val unit = decimal.get("unit").string() ?: return "ANSWER_TYPE"
    val scaleValue = decimal.get("scale")
    if (!scaleValue.isJsonPrimitive || !scaleValue.asJsonPrimitive.isNumber ||
        !integerToken.matches(scaleValue.asString)
    ) return "ANSWER_TYPE"
    val scale = scaleValue.integer()
    if (scale == null || scale !in 0L..6L || scale != field.get("scale").integer()) return "DECIMAL_SCALE"
    if (unit != field.text("unit")) return "DECIMAL_UNIT"
    val fraction = if (scale == 0L) "" else "\\.[0-9]{$scale}"
    val grammar = Regex("-?(0|[1-9][0-9]{0,11})$fraction")
    if (!grammar.matches(text) || text.startsWith('-') && text.drop(1).all { it == '0' || it == '.' }) {
        return "DECIMAL_FORMAT"
    }
    return null
}

private enum class Truth {
    TRUE, FALSE, UNKNOWN;

    fun not() = when (this) {
        TRUE -> FALSE
        FALSE -> TRUE
        UNKNOWN -> UNKNOWN
    }
}

private fun Boolean.truth() = if (this) Truth.TRUE else Truth.FALSE

private enum class State(val wire: String) {
    INACTIVE("inactive"), UNRESOLVED("unresolved"), OPTIONAL("optional"), REQUIRED("required");

    val active get() = this == OPTIONAL || this == REQUIRED
}

private data class Target(val kind: String, val item: String?, val id: String)

private data class Status(val visibility: Truth, val state: State)

private data class Candidate(
    val receipt: JsonObject,
    val target: Target?,
    val exact: Boolean
) {
    val id get() = receipt.text("receipt_id")
    val evidenceId get() = receipt.text("evidence_id")
    val eligible get() = receipt.get("eligible").asBoolean
}

private data class DataError(val code: String, val target: Target?, val receiptId: String? = null) {
    fun json(documentId: String) = jsonObject(
        "code" to code,
        "document_instance_id" to documentId.takeIf { target != null },
        "repeat_item_id" to target?.item,
        "field_id" to target?.id?.takeIf { target.kind == "field" },
        "slot_id" to target?.id?.takeIf { target.kind == "slot" },
        "receipt_id" to receiptId
    )
}

internal fun evaluate(basePackage: JsonObject, input: JsonObject): JsonObject {
    val pkg = resolvePackage(basePackage, input)
    val answers = input.obj("answers")
    val receipts = input.array("receipts")
    val config = configurationErrors(pkg, input)
    if (config.isNotEmpty()) {
        return result(answers, receipts, config.map { it.json() }.jsonArray())
    }
    return DocumentEvaluation(pkg, answers, receipts).evaluate()
}

private fun result(
    answers: JsonObject, receipts: JsonArray, config: JsonArray = JsonArray(),
    applicability: JsonArray = JsonArray(), document: JsonObject = JsonObject(), items: JsonArray = JsonArray(),
    bindings: JsonArray = JsonArray(), errors: JsonArray = JsonArray()
) = jsonObject(
    "configuration_errors" to config,
    "applicability" to applicability,
    "retained_answers" to answers,
    "retained_receipts" to receipts,
    "submission_projection" to jsonObject("document" to document, "items" to items),
    "evidence_bindings" to bindings,
    "errors" to errors,
    "can_submit" to (config.size() == 0 && errors.size() == 0)
)

private class DocumentEvaluation(
    private val pkg: JsonObject,
    private val answers: JsonObject,
    private val receipts: JsonArray
) {
    private val fields = pkg.array("fields").map { it.asJsonObject }.associateBy { it.text("id") }
    private val slots = pkg.array("slots").map { it.asJsonObject }.associateBy { it.text("id") }
    private val repeats = pkg.array("repeat_items").map { it.asString }
    private val statuses = mutableMapOf<Target, Status>()

    fun evaluate(): JsonObject {
        val targets = (listOf<String?>(null) + repeats).flatMap { item ->
            val scope = if (item == null) "document" else "item"
            fields.values.filter { it.text("scope") == scope }.map { Target("field", item, it.text("id")) } +
                slots.values.filter { fields.getValue(it.text("field_id")).text("scope") == scope }
                    .map { Target("slot", item, it.text("id")) }
        }
        // Field references are resolved lazily through the validated, acyclic dependency graph.
        val states = targets.associateWith { if (it.kind == "field") fieldStatus(it).state else slotStatus(it) }
        val projected = (listOf<String?>(null) + repeats).associateWith { JsonObject() }
        val errors = mutableListOf<DataError>()
        for ((target, state) in states) {
            if (state == State.UNRESOLVED) errors += DataError("UNRESOLVED_CONDITION", target)
            if (!state.active || target.kind != "field") continue
            val answer = readAnswer(target)
            val error = answerError(fields.getValue(target.id), answer, state == State.REQUIRED)
            if (error != null) errors += DataError(error, target)
            else if (answer != null) projected.getValue(target.item).add(target.id, answer)
        }

        val bindings = resolveEvidence(states, errors)
        val targetOrder = targets.withIndex().associate { it.value to it.index }
        val sortedErrors = errors.distinct().sortedWith(compareBy(
            { targetOrder[it.target] ?: Int.MAX_VALUE },
            { it.code == "REQUIRED_EVIDENCE_MISSING" },
            DataError::code,
            DataError::receiptId
        ))
        return result(
            answers = answers, receipts = receipts,
            applicability = states.map { (target, state) ->
                jsonObject("kind" to target.kind, "repeat_item_id" to target.item, "id" to target.id, "state" to state.wire)
            }.jsonArray(),
            document = projected.getValue(null),
            items = repeats.map { jsonObject("repeat_item_id" to it, "answers" to projected.getValue(it)) }.jsonArray(),
            bindings = targets.mapNotNull(bindings::get).jsonArray(),
            errors = sortedErrors.map { it.json(pkg.text("document_instance_id")) }.jsonArray()
        )
    }

    private fun readAnswer(target: Target): JsonElement? {
        val group = if (target.item == null) answers.obj("document")
            else answers.obj("items").get(target.item).objectValue()
        return group?.get(target.id)
    }

    private fun fieldStatus(target: Target): Status = statuses.getOrPut(target) {
        val field = fields.getValue(target.id)
        val visibility = field.get("visible_if")?.let { predicate(it, target.item) } ?: Truth.TRUE
        Status(visibility, stateFor(field, "required", target.item, visibility))
    }

    private fun slotStatus(target: Target): State {
        val slot = slots.getValue(target.id)
        val parent = fieldStatus(Target("field", target.item, slot.text("field_id"))).visibility
        val visibility = if (parent != Truth.TRUE) parent
            else slot.get("visible_if")?.let { predicate(it, target.item) } ?: Truth.TRUE
        return stateFor(slot, "is_required", target.item, visibility)
    }

    private fun stateFor(definition: JsonObject, requiredKey: String, item: String?, visibility: Truth): State =
        when (visibility) {
            Truth.FALSE -> State.INACTIVE
            Truth.UNKNOWN -> State.UNRESOLVED
            Truth.TRUE -> {
                if (definition.get(requiredKey).boolean() == true) State.REQUIRED
                else when (definition.get("required_if")?.let { predicate(it, item) } ?: Truth.FALSE) {
                    Truth.TRUE -> State.REQUIRED
                    Truth.FALSE -> State.OPTIONAL
                    Truth.UNKNOWN -> State.UNRESOLVED
                }
            }
        }

    private fun predicate(value: JsonElement, item: String?): Truth {
        val (operator, argument) = value.asJsonObject.entrySet().single()
        return when (operator) {
            "all", "any" -> {
                val shortCircuit = if (operator == "all") Truth.FALSE else Truth.TRUE
                var unknown = false
                for (child in argument.asJsonArray) {
                    val truth = predicate(child, item)
                    if (truth == shortCircuit) return truth
                    if (truth == Truth.UNKNOWN) unknown = true
                }
                if (unknown) Truth.UNKNOWN else shortCircuit.not()
            }
            "not" -> predicate(argument, item).not()
            "present", "is_null", "eq" -> {
                val ref = if (operator == "eq") argument.asJsonArray[0].asJsonObject else argument.asJsonObject
                val target = Target("field", item.takeIf { ref.text("scope") == "item" }, ref.text("field"))
                if (fieldStatus(target).visibility != Truth.TRUE) return Truth.UNKNOWN
                val answer = readAnswer(target)
                when (operator) {
                    "present" -> (answer != null).truth()
                    "is_null" -> (answer?.isJsonNull == true).truth()
                    else -> {
                        if (answer == null || answerError(fields.getValue(target.id), answer, required = false) != null) {
                            Truth.UNKNOWN
                        } else (answer == argument.asJsonArray[1]).truth()
                    }
                }
            }
            else -> error("Unvalidated operator: $operator")
        }
    }

    private fun resolveEvidence(states: Map<Target, State>, errors: MutableList<DataError>): Map<Target, JsonObject> {
        val candidates = receipts.map { it.asJsonObject }.distinct().map { receipt ->
            val target = Target("slot", receipt.get("for_repeat_item_id").string(), receipt.text("for_slot_id"))
                .takeIf(states::containsKey)
            Candidate(receipt, target, target != null && exactTarget(receipt, target))
        }
        val conflicts = mutableSetOf<Candidate>()
        for (grouping in listOf(candidates.groupBy(Candidate::id), candidates.groupBy(Candidate::evidenceId))) {
            grouping.values.filter { it.size > 1 }.forEach(conflicts::addAll)
        }
        candidates.filter { it.target != null && it.exact && it.eligible && states.getValue(it.target).active }
            .groupBy(Candidate::target).values.filter { it.size > 1 }.forEach(conflicts::addAll)

        val accepted = mutableMapOf<Target, JsonObject>()
        for (candidate in candidates) {
            val target = candidate.target
            val code = when {
                target == null -> "EVIDENCE_TARGET_MISMATCH"
                candidate in conflicts -> "EVIDENCE_CONFLICT"
                !candidate.exact -> "EVIDENCE_TARGET_MISMATCH"
                states.getValue(target) == State.INACTIVE -> null
                !candidate.eligible -> "EVIDENCE_INELIGIBLE"
                else -> null
            }
            if (code != null) errors += DataError(code, target, candidate.id)
            else if (target != null && states.getValue(target).active) {
                accepted[target] = candidate.receipt.deepCopy().apply {
                    remove("for_repeat_item_id")
                    remove("for_slot_id")
                    remove("eligible")
                }
            }
        }
        states.filter { (target, state) -> target.kind == "slot" && state == State.REQUIRED && target !in accepted }
            .keys.forEach { errors += DataError("REQUIRED_EVIDENCE_MISSING", it) }
        return accepted
    }

    private fun exactTarget(receipt: JsonObject, target: Target): Boolean =
        packageScope.all { receipt.get(it) == pkg.get(it) } &&
            receipt.get("field_id") == slots.getValue(target.id).get("field_id") &&
            receipt.get("slot_id") == JsonPrimitive(target.id) &&
            receipt.get("repeat_item_id").string() == target.item
}
