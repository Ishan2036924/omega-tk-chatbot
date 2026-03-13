"""
Layer 3 Guardrail — code validation pipeline.

Three checks run in sequence on every generated code block:
  1. Syntax     — ast.parse() catches broken Python syntax
  2. Pattern    — regex confirms the 5-step OpenEye workflow is present
  3. API names  — allowlist catches hallucinated oeomega.* / oechem.* names

Each check returns (is_valid: bool, failure_reason: str).
validate_code() runs all three and returns the first failure, or (True, "").
"""

import ast
import re

# ── Allowlists ──────────────────────────────────────────────────────────────
# Easy to extend: just add names to the relevant set.

VALID_OEOMEGA_NAMES = {
    # Conformer generation
    "OEOmega", "OEOmegaOptions",
    "OEOmegaSampling_Classic", "OEOmegaSampling_Dense",
    "OEOmegaSampling_Pose", "OEOmegaSampling_ROCS", "OEOmegaSampling_FastROCS",
    # Stereochemistry
    "OEFlipper", "OEFlipperOptions",
    # Macrocycles
    "OEMacrocycleOmega", "OEMacrocycleOmegaOptions", "OEIsMacrocycle",
    # Torsion drive
    "OETorDriver", "OETorDriveOptions",
    # Error handling
    "OEGetOmegaError",
    "OEOmegaReturnCode_Success", "OEOmegaReturnCode_Failed",
    "OEOmegaReturnCode_Undefined",
    # Advanced options
    "OEConfFixOptions", "OEMolBuilder",
}

VALID_OECHEM_NAMES = {
    # Molecule classes
    "OEMol", "OEGraphMol", "OESmiles",
    # I/O streams  (note: lowercase first letter is correct)
    "oemolistream", "oemolostream",
    # Molecule I/O
    "OEReadMolecule", "OEWriteMolecule", "OEGetDefaultMol",
    # SMILES utilities
    "OESmilesToMol", "OEMolToSmiles", "OEParseSmiles", "OECreateSmiString",
    # Hydrogen handling
    "OEAddHydrogens", "OESuppressHydrogens",
    # Aromaticity / perception
    "OEAssignAromaticFlags", "OEAssignHybridization",
    # Format utilities
    "OEGetMolFileExtension",
    # InChI
    "OEGetInChI", "OEInChIToMol",
    # Misc utilities that appear in examples
    "OEGetTitle", "OESetTitle",
}

# ── Pattern check ────────────────────────────────────────────────────────────
# Each entry: (regex, human-readable label)
PATTERN_CHECKS = [
    (r"from openeye import",                              "openeye imports"),
    (r"oemolistream|oemolostream",                        "molecule streams"),
    (r"OEOmegaOptions|OEFlipperOptions|OEMacrocycleOmegaOptions", "options declaration"),
    (r"\.Build\(",                                        "omega.Build() call"),
    (r"OEOmegaReturnCode|OEGetOmegaError",                "error handling"),
]

MIN_PATTERN_MATCHES = 3   # pass if at least this many checks hit


# ── Individual checks ────────────────────────────────────────────────────────

def check_syntax(code: str) -> tuple[bool, str]:
    """Check 1: valid Python syntax via ast.parse()."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as exc:
        return False, (
            f"Your previous code had a syntax error on line {exc.lineno}: {exc.msg}. "
            "Please fix the syntax and generate corrected code."
        )


def check_pattern(code: str) -> tuple[bool, str]:
    """Check 2: at least MIN_PATTERN_MATCHES of the 5-step OpenEye workflow."""
    matched = [label for pattern, label in PATTERN_CHECKS if re.search(pattern, code)]
    if len(matched) >= MIN_PATTERN_MATCHES:
        return True, ""

    missing = [label for pattern, label in PATTERN_CHECKS
               if not re.search(pattern, code)]
    return False, (
        f"Your previous code was missing required OpenEye patterns: {', '.join(missing)}. "
        "Include the complete 5-step OpenEye pattern: imports, molecule streams, "
        "options declaration, omega.Build() call, and error handling."
    )


def check_api_names(code: str) -> tuple[bool, str]:
    """Check 3: all oeomega.* and oechem.* references are in the allowlist."""
    oeomega_refs = set(re.findall(r"oeomega\.(\w+)", code))
    oechem_refs  = set(re.findall(r"oechem\.(\w+)", code))

    invalid_oeomega = oeomega_refs - VALID_OEOMEGA_NAMES
    invalid_oechem  = oechem_refs  - VALID_OECHEM_NAMES
    invalid = invalid_oeomega | invalid_oechem

    if not invalid:
        return True, ""

    return False, (
        f"Your previous code used unknown API names that may be hallucinated: "
        f"{', '.join(sorted(invalid))}. "
        "Use only documented OpenEye Omega Toolkit APIs."
    )


# ── Public entry point ────────────────────────────────────────────────────────

def validate_code(code: str) -> tuple[bool, str]:
    """
    Run all three checks in sequence.

    Returns:
        (True, "")               — all checks passed
        (False, failure_reason)  — first failing check, with a retry instruction
    """
    for check_fn in (check_syntax, check_pattern, check_api_names):
        ok, reason = check_fn(code)
        if not ok:
            return False, reason
    return True, ""
