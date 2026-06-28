def get_confidence_tier(confidence: float) -> str:
    """
    Return confidence tier string based on score.
    - 'green'  for confidence > 0.95
    - 'yellow' for confidence in [0.80, 0.95]
    - 'red'    for confidence < 0.80
    """
    if confidence > 0.95:
        return "green"
    elif confidence >= 0.80:
        return "yellow"
    else:
        return "red"
