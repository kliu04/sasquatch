CLASS_NAMES = ["hold", "volume"]
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
ALLOWED_HOLD_TYPES = {
    "crimp",
    "jug",
    "sloper",
    "pinch",
    "pocket",
    "edge",
    "not-hold",
}

GEMINI_SYSTEM_PROMPT = (
    "Classify this climbing hold. Some holds that are labeled holds are not holds, "
    "they are tape or other stuff.\n\n"
    "Type: crimp/jug/sloper/pinch/pocket/edge/not-hold\n"
    "Report as JSON"
)

BATCH_GEMINI_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "instance_id": {"type": "integer"},
            "type": {"type": "string"},
        },
        "propertyOrdering": ["instance_id", "type"],
        "required": ["instance_id", "type"],
    },
}

SINGLE_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
    },
    "propertyOrdering": ["type"],
    "required": ["type"],
}

TYPE_COLORS_BGR = {
    "crimp": (20, 80, 180),
    "jug": (35, 130, 60),
    "sloper": (180, 120, 0),
    "pinch": (120, 55, 170),
    "pocket": (45, 150, 150),
    "edge": (170, 85, 40),
    "not-hold": (80, 80, 80),
    "unclassified": (0, 150, 180),
}
