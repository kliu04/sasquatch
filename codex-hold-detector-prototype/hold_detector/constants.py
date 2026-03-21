CLASS_NAMES = ["hold", "volume"]
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
GEMINI_SYSTEM_PROMPT = (
    "Look at this climbing hold crop. Determine if the detected region is tape "
    "(route tape, hold-marking tape, or other non-hold tape) rather than an actual climbing hold.\n\n"
    "Report as JSON with a single boolean field: is_tape"
)

SINGLE_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "is_tape": {"type": "boolean"},
    },
    "propertyOrdering": ["is_tape"],
    "required": ["is_tape"],
}

