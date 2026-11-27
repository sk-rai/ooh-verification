package trustcapture.gate2

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive
import com.google.gson.Strictness
import com.google.gson.internal.LazilyParsedNumber
import com.google.gson.stream.JsonReader
import com.google.gson.stream.JsonToken
import java.io.IOException
import java.io.StringReader

internal val identifier = Regex("[A-Za-z][A-Za-z0-9_-]{0,63}")
internal val integerToken = Regex("-?(0|[1-9][0-9]*)")
internal const val profile = "tc-inspection-semantics-v1"
internal val headerKeys = setOf("fixture_version", "profile", "fixture_id", "package", "cases")

internal class Rejected(val code: String, path: String) : IllegalArgumentException("$code at $path")

internal fun decodeJson(text: String): JsonElement {
    if (text.startsWith('\uFEFF')) throw Rejected("INVALID_JSON", "$")
    val reader = JsonReader(StringReader(text)).apply { strictness = Strictness.STRICT }
    try {
        val value = reader.readValue()
        if (reader.peek() != JsonToken.END_DOCUMENT) throw Rejected("INVALID_JSON", reader.path)
        return value
    } catch (_: IOException) {
        throw Rejected("INVALID_JSON", reader.path)
    }
}

private fun JsonReader.readValue(): JsonElement = when (peek()) {
    JsonToken.BEGIN_OBJECT -> JsonObject().also { result ->
        beginObject()
        while (hasNext()) {
            val key = nextName().requireValidUnicode(path)
            if (result.has(key)) throw Rejected("DUPLICATE_KEY", path)
            result.add(key, readValue())
        }
        endObject()
    }
    JsonToken.BEGIN_ARRAY -> JsonArray().also { result ->
        beginArray()
        while (hasNext()) result.add(readValue())
        endArray()
    }
    JsonToken.STRING -> JsonPrimitive(nextString().requireValidUnicode(path))
    JsonToken.NUMBER -> JsonPrimitive(LazilyParsedNumber(nextString()))
    JsonToken.BOOLEAN -> JsonPrimitive(nextBoolean())
    JsonToken.NULL -> { nextNull(); JsonNull.INSTANCE }
    else -> throw Rejected("INVALID_JSON", path)
}

private fun String.requireValidUnicode(path: String): String {
    var index = 0
    while (index < length) {
        val char = this[index++]
        if (char.isLowSurrogate()) throw Rejected("INVALID_JSON", path)
        if (char.isHighSurrogate() && (index == length || !this[index++].isLowSurrogate())) {
            throw Rejected("INVALID_JSON", path)
        }
    }
    return this
}

internal fun JsonElement?.string(): String? =
    this?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString
internal fun JsonElement?.boolean(): Boolean? =
    this?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isBoolean }?.asBoolean
internal fun JsonElement?.integer(): Long? =
    this?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isNumber && integerToken.matches(it.asString) }
        ?.asString?.toLongOrNull()
internal fun JsonElement?.objectValue(): JsonObject? = this?.takeIf { it.isJsonObject }?.asJsonObject
internal fun JsonElement?.arrayValue(): JsonArray? = this?.takeIf { it.isJsonArray }?.asJsonArray
internal fun JsonObject.text(name: String): String = requireNotNull(get(name).string()) { "Expected string: $name" }
internal fun JsonObject.obj(name: String): JsonObject = requireNotNull(get(name).objectValue()) { "Expected object: $name" }
internal fun JsonObject.array(name: String): JsonArray = requireNotNull(get(name).arrayValue()) { "Expected array: $name" }

internal fun jsonObject(vararg values: Pair<String, Any?>): JsonObject = JsonObject().apply {
    values.forEach { (name, value) ->
        add(name, when (value) {
            null -> JsonNull.INSTANCE
            is JsonElement -> value
            is String -> JsonPrimitive(value)
            is Boolean -> JsonPrimitive(value)
            else -> error("Unsupported JSON output type")
        })
    }
}

internal fun Iterable<JsonElement>.jsonArray(): JsonArray = JsonArray().also { result -> forEach(result::add) }

internal fun headerError(value: JsonElement): String? {
    val header = value.objectValue() ?: return "INVALID_TYPE"
    if (header.keySet().any { it !in headerKeys }) return "UNKNOWN_PROPERTY"
    if (!header.has("fixture_version") || !header.has("profile")) return "MISSING_PROPERTY"
    val number = header.get("fixture_version")
    if (!number.isJsonPrimitive || !number.asJsonPrimitive.isNumber || !integerToken.matches(number.asString)) {
        return "INVALID_INTEGER"
    }
    val actualProfile = header.get("profile").string() ?: return "INVALID_TYPE"
    return if (number.asString != "1" || actualProfile != profile) "UNSUPPORTED_VERSION" else null
}

internal fun capabilityError(value: JsonElement): String? {
    val values = value.arrayValue() ?: return "INVALID_TYPE"
    if (values.any { it.string()?.let(identifier::matches) != true }) return "INVALID_ID"
    return if (values.map { it.asString }.toSet().size != values.size()) "DUPLICATE_CAPABILITY" else null
}

internal fun checkParser(check: String, input: String): String? {
    val value = try { decodeJson(input) } catch (error: Rejected) { return error.code }
    return when (check) {
        "json" -> null
        "fixture_header" -> headerError(value)
        "identifier" -> if (value.string()?.let(identifier::matches) == true) null else "INVALID_ID"
        "capabilities" -> capabilityError(value)
        else -> error("Unknown parser check: $check")
    }
}
