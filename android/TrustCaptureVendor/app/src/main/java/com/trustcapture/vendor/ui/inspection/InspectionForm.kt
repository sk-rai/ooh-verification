package com.trustcapture.vendor.ui.inspection

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive
import com.trustcapture.vendor.data.remote.dto.InspectionCaptureTargetDto
import com.trustcapture.vendor.data.remote.dto.InspectionPackageDocumentDto

data class InspectionAnswerKey(val repeatItemId: String, val fieldId: String)

internal data class InspectionField(
    val id: String,
    val label: String,
    val type: String,
    val required: Boolean,
    val scale: Int?,
    val unit: String?
) {
    fun encode(input: String): JsonElement? = when (type) {
        "text" -> JsonPrimitive(input)
        "boolean" -> when (input) {
            "true" -> JsonPrimitive(true)
            "false" -> JsonPrimitive(false)
            else -> null
        }
        "number" -> {
            val fraction = if (scale == 0) "" else "\\.[0-9]{$scale}"
            val valid = input.length <= 80 && Regex("-?(?:0|[1-9][0-9]*)$fraction").matches(input)
            if (valid) JsonObject().apply {
                addProperty("value", input)
                addProperty("scale", scale)
                addProperty("unit", unit)
            } else null
        }
        else -> null
    }
}

internal data class InspectionRepeatForm(val itemIds: List<String>, val fields: List<InspectionField>) {
    companion object {
        fun parse(definition: JsonObject): InspectionRepeatForm? {
            val items = definition["repeat_items"]?.takeIf { it.isJsonArray }?.asJsonArray ?: return null
            val rules = definition["repeat_fields"]?.takeIf { it.isJsonObject }?.asJsonObject ?: return null
            val itemIds = items.map { it.stringValue() ?: return null }
            if (itemIds.toSet().size != itemIds.size) return null
            val fields = rules.entrySet().map { (id, rule) ->
                val field = rule.takeIf { it.isJsonObject }?.asJsonObject ?: return null
                val type = field["type"].stringValue() ?: return null
                if (type !in setOf("text", "number", "boolean")) return null
                val scale = field["scale"]?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isNumber }
                    ?.asString?.toIntOrNull()
                val unit = field["unit"].stringValue()
                if (type == "number" && (scale == null || scale !in 0..18 || unit.isNullOrEmpty())) return null
                val required = field["required"]?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isBoolean }
                    ?.asBoolean ?: false
                InspectionField(id, field["label"].stringValue() ?: id, type, required, scale, unit)
            }
            return InspectionRepeatForm(itemIds, fields)
        }
    }
}

private fun JsonElement?.stringValue(): String? =
    this?.takeIf { it.isJsonPrimitive && it.asJsonPrimitive.isString }?.asString

@Composable
fun InspectionForm(
    document: InspectionPackageDocumentDto,
    answers: Map<InspectionAnswerKey, String>,
    onAnswerChanged: (InspectionAnswerKey, String) -> Unit,
    modifier: Modifier = Modifier,
    onCapture: ((InspectionCaptureTargetDto) -> Unit)? = null,
    readOnly: Boolean = false
) {
    val form = remember(document.definition) { InspectionRepeatForm.parse(document.definition) }
    if (form == null) {
        Text("This form is unsupported.", modifier)
        return
    }

    LazyColumn(modifier = modifier, verticalArrangement = Arrangement.spacedBy(16.dp)) {
        itemsIndexed(form.itemIds, key = { _, itemId -> itemId }) { index, itemId ->
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Observation ${index + 1}", style = MaterialTheme.typography.titleMedium)
                form.fields.forEach { field ->
                    val key = InspectionAnswerKey(itemId, field.id)
                    val answer = answers[key]
                    val label = if (field.required) "${field.label} (required)" else field.label
                    when (field.type) {
                        "boolean" -> {
                            Text(label)
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                FilterChip(answer == "true", { onAnswerChanged(key, "true") }, { Text("Yes") }, enabled = !readOnly)
                                FilterChip(answer == "false", { onAnswerChanged(key, "false") }, { Text("No") }, enabled = !readOnly)
                            }
                        }
                        else -> {
                            val invalid = field.type == "number" && !answer.isNullOrEmpty() && field.encode(answer) == null
                            OutlinedTextField(
                                value = answer.orEmpty(),
                                onValueChange = { onAnswerChanged(key, it) },
                                readOnly = readOnly,
                                label = { Text(label) },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = field.type == "number",
                                isError = invalid,
                                supportingText = field.unit?.let { unit ->
                                    { Text("$unit · ${field.scale} decimal places") }
                                }
                            )
                        }
                    }
                }
                document.captureTargets.filter { it.repeatItemId == itemId }.forEach { target ->
                    Button(onClick = { onCapture?.invoke(target) }, enabled = !readOnly && onCapture != null) {
                        val requirement = if (target.required) "Required photo" else "Add photo"
                        Text("$requirement · ${target.slotId}")
                    }
                }
            }
        }
    }
}
