from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
LOW_EFFORT_METHODS = {"slow-cooker", "minimal-cook", "no-cook"}
MAX_PROTEIN_PER_WEEK = 3
MAX_OPTION_OVERLAP = 2
MAX_USER_IDEAS_PER_WEEK = 2
