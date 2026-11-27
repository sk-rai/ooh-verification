package trustcapture.gate2

import com.google.gson.JsonElement
import com.google.gson.JsonObject

internal val packageScope = listOf(
    "tenant_id", "owner_client_id", "vendor_id", "visit_id", "assignment_id", "generation", "document_instance_id"
)
private val packageKeys = packageScope.toSet() + setOf(
    "form_version_id", "rule_version", "required_capabilities", "repeat_items", "fields", "slots"
)
private val supported = setOf("repeat-same-item", "conditional-photo", "fixed-scale-decimal")
private val fieldKeys = setOf("id", "scope", "type", "required", "visible_if", "required_if")
private val slotKeys = setOf("id", "field_id", "is_required", "visible_if", "required_if")
private val externalKeys = setOf("url", "resource", "external_url", "resource_url")
private val ruleKeys = listOf("visible_if", "required_if")
internal const val maxSafeInteger = 9_007_199_254_740_991L

internal data class ConfigurationError(val code: String, val subject: String?) {
    fun json() = jsonObject("code" to code, "subject_id" to subject)
}

internal fun resolvePackage(base: JsonObject, input: JsonObject): JsonObject = base.deepCopy().apply {
    input.get("package_override").objectValue()?.entrySet()?.forEach { (key, value) -> add(key, value) }
}

internal fun configurationErrors(pkg: JsonObject, input: JsonObject): List<ConfigurationError> {
    val errors = mutableSetOf<ConfigurationError>()
    fun reject(code: String, subject: String? = null) { errors += ConfigurationError(code, subject) }
    val capabilities = pkg.get("required_capabilities").arrayValue()
    val repeats = pkg.get("repeat_items").arrayValue()
    val fields = pkg.get("fields").arrayValue()
    val slots = pkg.get("slots").arrayValue()
    val version = pkg.get("rule_version").integer()
    if (pkg.keySet() != packageKeys || capabilities == null || repeats == null || fields == null || slots == null ||
        version == null || version !in 1..maxSafeInteger ||
        pkg.get("generation").integer()?.let { it in 1..maxSafeInteger } != true ||
        (packageScope - "generation" + "form_version_id").any { !validId(pkg.get(it)) } ||
        capabilityError(capabilities) != null || capabilityError(repeats) != null ||
        repeats.size() > 16 || fields.size() > 32 || slots.size() > 16
    ) return listOf(ConfigurationError("INVALID_PACKAGE", null))

    if (version != 1L) reject("UNSUPPORTED_VERSION")
    val clientCapabilities = input.array("client_capabilities").map { it.asString }.toSet()
    capabilities.map { it.asString }.filter { it !in supported || it !in clientCapabilities }
        .forEach { reject("UNSUPPORTED_CAPABILITY", it) }
    val replacement = input.get("published_replacement").objectValue()
    if (replacement != null && replacement.get("form_version_id") == pkg.get("form_version_id") && replacement != pkg) {
        reject("PUBLISHED_VERSION_CHANGED", pkg.text("form_version_id"))
    }

    val fieldsById = linkedMapOf<String, JsonObject>()
    val slotsById = linkedMapOf<String, JsonObject>()
    val targetIds = mutableSetOf<String>()
    for (entry in fields) {
        val field = entry.objectValue()
        val id = field?.get("id").string()
        if (field == null || id == null || !identifier.matches(id) || !targetIds.add(id)) {
            reject("INVALID_PACKAGE", id)
        } else if (field.hasExternalProperty()) {
            reject("EXTERNAL_REFERENCE_FORBIDDEN", id)
            // Keep the declared field available for resolving references from other targets.
            fieldsById[id] = field
        } else if (!validField(field)) {
            reject("INVALID_PACKAGE", id)
        } else {
            fieldsById[id] = field
        }
    }
    for (entry in slots) {
        val slot = entry.objectValue()
        val id = slot?.get("id").string()
        if (slot == null || id == null || !identifier.matches(id) || !targetIds.add(id)) {
            reject("INVALID_PACKAGE", id)
        } else if (slot.hasExternalProperty()) {
            reject("EXTERNAL_REFERENCE_FORBIDDEN", id)
        } else if (slot.keySet().any { it !in slotKeys } || slot.get("field_id").string() !in fieldsById ||
            slot.has("is_required") && slot.get("is_required").boolean() == null
        ) {
            reject("INVALID_PACKAGE", id)
        } else {
            slotsById[id] = slot
        }
    }

    val dependencies = fieldsById.keys.associateWith { mutableSetOf<String>() }
    val targets = fieldsById + slotsById
    if (targets.values.sumOf { target -> ruleKeys.count(target::has) } > 64) reject("RULE_LIMIT")
    for ((id, target) in targets) {
        if (target.hasExternalProperty()) continue
        val field = fieldsById[id] ?: fieldsById[target.get("field_id").string()] ?: continue
        val scope = field.get("scope").string() ?: continue
        for (key in ruleKeys) {
            if (!target.has(key)) continue
            val scan = PredicateScan(fieldsById, scope)
            val code = scan.validate(target.get(key))
            if (code != null) reject(code, id)
            else dependencies[id]?.addAll(scan.references)
        }
    }
    for (component in cyclicComponents(dependencies)) reject("RULE_CYCLE", component.min())
    return errors.sortedWith(compareBy(ConfigurationError::code, ConfigurationError::subject))
}

private fun validId(value: JsonElement?): Boolean = value.string()?.let(identifier::matches) == true

private fun validField(field: JsonObject): Boolean {
    val type = field.get("type").string()
    val extras = when (type) {
        "boolean", "text" -> emptySet()
        "enum" -> {
            val options = field.get("options").arrayValue() ?: return false
            if (options.isEmpty || capabilityError(options) != null) return false
            setOf("options")
        }
        "decimal" -> {
            val scale = field.get("scale").integer() ?: return false
            if (scale !in 0L..6L || !validId(field.get("unit"))) return false
            setOf("scale", "unit")
        }
        else -> return false
    }
    return field.get("scope").string() in setOf("document", "item") &&
        field.keySet().all { it in fieldKeys || it in extras } &&
        (!field.has("required") || field.get("required").boolean() != null)
}

private fun JsonObject.hasExternalProperty(): Boolean = keySet().any { it in externalKeys }

private class PredicateScan(private val fields: Map<String, JsonObject>, private val scope: String) {
    private var nodes = 0
    val references = mutableSetOf<String>()

    fun validate(value: JsonElement, depth: Int = 1): String? {
        if (++nodes > 64 || depth > 8) return "RULE_LIMIT"
        val node = value.objectValue() ?: return "INVALID_RULE"
        if (node.hasExternalProperty()) return "EXTERNAL_REFERENCE_FORBIDDEN"
        val (operator, argument) = node.entrySet().singleOrNull() ?: return "INVALID_RULE"
        return when (operator) {
            "all", "any" -> {
                val children = argument.arrayValue() ?: return "INVALID_RULE"
                if (children.size() !in 1..8) return "RULE_LIMIT"
                children.firstNotNullOfOrNull { validate(it, depth + 1) }
            }
            "not" -> validate(argument, depth + 1)
            "present", "is_null" -> validateReference(argument)
            "eq" -> {
                val pair = argument.arrayValue()?.takeIf { it.size() == 2 } ?: return "INVALID_RULE"
                validateReference(pair[0])?.let { return it }
                val field = fields.getValue(pair[0].asJsonObject.text("field"))
                if (answerError(field, pair[1], required = false) == null) null else "INVALID_RULE"
            }
            else -> "INVALID_RULE"
        }
    }

    private fun validateReference(value: JsonElement): String? {
        val ref = value.objectValue()?.takeIf { it.keySet() == setOf("scope", "field") }
            ?: return "INVALID_FIELD_REFERENCE"
        val id = ref.get("field").string() ?: return "INVALID_FIELD_REFERENCE"
        val refScope = ref.get("scope").string()
        if (refScope !in setOf("document", "item") || fields[id]?.get("scope").string() != refScope ||
            scope == "document" && refScope == "item"
        ) return "INVALID_FIELD_REFERENCE"
        references += id
        return null
    }
}

// At most 32 fields. Mutual reachability groups each cyclic component without recursion.
private fun cyclicComponents(edges: Map<String, Set<String>>): List<Set<String>> {
    val reachable = edges.keys.associateWith { start ->
        val seen = mutableSetOf<String>()
        val pending = ArrayDeque(edges.getValue(start))
        while (pending.isNotEmpty()) {
            val next = pending.removeFirst()
            if (seen.add(next)) pending.addAll(edges[next].orEmpty())
        }
        seen
    }
    val unreported = edges.keys.filter { it in reachable.getValue(it) }.toMutableSet()
    return buildList {
        while (unreported.isNotEmpty()) {
            val first = unreported.first()
            val component = unreported.filterTo(mutableSetOf()) {
                it in reachable.getValue(first) && first in reachable.getValue(it)
            }
            add(component)
            unreported.removeAll(component)
        }
    }
}
