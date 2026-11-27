package trustcapture.gate2

import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.name
import kotlin.system.exitProcess

private const val parserFile = "input-rejections.json"
private val caseKeys = setOf("id", "client_capabilities", "display_order", "answers", "receipts", "expected")
private val optionalCaseKeys = setOf("package_override", "published_replacement")

fun main(args: Array<String>) {
    if (args.size > 1) {
        System.err.println("Usage: trustcapture-gate2-kotlin [fixture-directory]")
        exitProcess(2)
    }
    val root = Path.of(args.singleOrNull() ?: "../../fixtures/v1")
    try {
        val counts = runFixtures(root)
        println("Workflow: ${counts.workflow.passed}/${counts.workflow.total} passed")
        println("Parser: ${counts.parser.passed}/${counts.parser.total} passed")
        val failed = counts.workflow.total + counts.parser.total - counts.workflow.passed - counts.parser.passed
        println("Discrepancies: $failed")
        if (failed != 0) exitProcess(1)
    } catch (error: Exception) {
        System.err.println("Fixture runner failed: ${error.message}")
        exitProcess(2)
    }
}

private data class Count(var passed: Int = 0, var total: Int = 0)
private data class Counts(val workflow: Count = Count(), val parser: Count = Count())

private fun runFixtures(root: Path): Counts {
    val counts = Counts()
    val workflowFiles = Files.list(root).use { stream ->
        stream.filter { it.name.endsWith(".json") && !it.name.endsWith(".schema.json") && it.name != parserFile }
            .sorted().toList()
    }
    require(workflowFiles.isNotEmpty()) { "No workflow files in $root" }
    for (path in workflowFiles) {
        val fixture = readFixture(path)
        require(headerError(fixture) == null && fixture.keySet() == headerKeys &&
            validIdentifier(fixture.get("fixture_id"))) { "${path.name}: invalid workflow header" }
        val pkg = fixture.obj("package")
        val loadedCases = uniqueCases(fixture, path)
        for (case in loadedCases) {
            val label = "${path.name} case=${case.text("id")}"
            compareCase(counts.workflow, label, case.get("expected")) {
                validateCase(case, pkg)
                val input = case.deepCopy().apply { remove("expected") }
                evaluate(pkg, input)
            }
        }
    }
    val manifest = readFixture(root.resolve(parserFile))
    require(headerError(manifest) == null && manifest.keySet() == setOf("fixture_version", "profile", "cases")) {
        "$parserFile: invalid parser manifest header"
    }
    for (case in uniqueCases(manifest, root.resolve(parserFile))) {
        val label = "$parserFile case=${case.text("id")}"
        compareCase(counts.parser, label, case.get("expected_code")) {
            require(case.keySet() == setOf("id", "check", "input", "expected_code")) { "Invalid parser case shape" }
            checkParser(case.text("check"), case.text("input"))?.let(::JsonPrimitive) ?: JsonNull.INSTANCE
        }
    }
    return counts
}

private fun readFixture(path: Path): JsonObject = try {
    decodeJson(Files.readString(path)).objectValue() ?: error("Expected a top-level object")
} catch (error: Exception) {
    throw IllegalArgumentException("${path.name}: ${error.message}", error)
}

private fun uniqueCases(fixture: JsonObject, path: Path): List<JsonObject> {
    val cases = fixture.array("cases").map { requireNotNull(it.objectValue()) { "${path.name}: invalid case" } }
    require(cases.isNotEmpty() && cases.all { validIdentifier(it.get("id")) } &&
        cases.map { it.text("id") }.toSet().size == cases.size
    ) { "${path.name}: missing cases, invalid IDs, or duplicate IDs" }
    return cases
}

private fun validateCase(case: JsonObject, pkg: JsonObject) {
    require(case.keySet().containsAll(caseKeys) && case.keySet().all { it in caseKeys || it in optionalCaseKeys })
    require(capabilityError(case.array("client_capabilities")) == null)
    val order = case.array("display_order")
    require(capabilityError(order) == null &&
        order.map { it.asString }.toSet() == pkg.array("repeat_items").map { it.asString }.toSet())
    val answers = case.obj("answers")
    require(answers.keySet() == setOf("document", "items"))
    require(answers.obj("document").keySet().all(identifier::matches))
    require(answers.obj("items").entrySet().all { (id, value) ->
        identifier.matches(id) && value.objectValue()?.keySet()?.all(identifier::matches) == true
    })
    val receiptIdKeys = (packageScope - "generation") + listOf(
        "field_id", "slot_id", "receipt_id", "evidence_id", "for_slot_id"
    )
    val nullable = listOf("repeat_item_id", "for_repeat_item_id")
    val expectedReceiptKeys = (receiptIdKeys + nullable + listOf("eligible", "generation")).toSet()
    val receipts = case.array("receipts")
    require(receipts.size() <= 64)
    for (value in receipts) {
        val receipt = requireNotNull(value.objectValue())
        require(receipt.keySet() == expectedReceiptKeys && receiptIdKeys.all { validIdentifier(receipt.get(it)) })
        require(nullable.all { receipt.get(it).isJsonNull || validIdentifier(receipt.get(it)) })
        require(receipt.get("eligible").boolean() != null &&
            receipt.get("generation").integer()?.let { it in 1..maxSafeInteger } == true)
    }
    require(optionalCaseKeys.all { !case.has(it) || case.get(it).isJsonObject })
}

private fun validIdentifier(value: JsonElement?) = value.string()?.let(identifier::matches) == true

private fun compareCase(count: Count, label: String, expected: JsonElement?, compute: () -> JsonElement) {
    count.total++
    val actual = try { compute() } catch (error: Exception) {
        System.err.println("FAIL $label pointer=\"\" evaluation error: ${error.message.orEmpty()}")
        return
    }
    val difference = firstDifference(expected, actual)
    if (difference == null) count.passed++
    else System.err.println("FAIL $label pointer=\"${difference.pointer}\" expected=${difference.expected} actual=${difference.actual}")
}

private data class Difference(val pointer: String, val expected: JsonElement?, val actual: JsonElement?)

private fun firstDifference(expected: JsonElement?, actual: JsonElement?, pointer: String = ""): Difference? {
    if (expected == null || actual == null) return if (expected == actual) null else Difference(pointer, expected, actual)
    if (expected.isJsonObject && actual.isJsonObject) {
        val a = expected.asJsonObject
        val b = actual.asJsonObject
        for (key in (a.keySet() + b.keySet()).sorted()) {
            val escaped = key.replace("~", "~0").replace("/", "~1")
            firstDifference(a.get(key), b.get(key), "$pointer/$escaped")?.let { return it }
        }
        return null
    }
    if (expected.isJsonArray && actual.isJsonArray) {
        val a = expected.asJsonArray
        val b = actual.asJsonArray
        for (i in 0 until maxOf(a.size(), b.size())) {
            val left = if (i < a.size()) a[i] else null
            val right = if (i < b.size()) b[i] else null
            firstDifference(left, right, "$pointer/$i")?.let { return it }
        }
        return null
    }
    if (expected.isJsonPrimitive && actual.isJsonPrimitive &&
        expected.asJsonPrimitive.isNumber && actual.asJsonPrimitive.isNumber
    ) {
        return if (expected.asBigDecimal.compareTo(actual.asBigDecimal) == 0) null
            else Difference(pointer, expected, actual)
    }
    return if (expected == actual) null else Difference(pointer, expected, actual)
}
