"""
Mathematical utilities for KPI scoring engine.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from datetime import date, timedelta
from calendar import monthrange
import logging

from .models import KPI, KPIValue, KPIScore, ReportingPeriod
from .dsl import Tokenizer, Parser, Evaluator



def compute_kpi_score(kpi: KPI, kpi_value: KPIValue) -> KPIScore:
    """
    Compute and create a KPIScore for a given KPI and KPIValue.
    
    Args:
        kpi: The KPI instance
        kpi_value: The KPIValue instance with actual, target, baseline values
        
    Returns:
        KPIScore instance
    """
    config = kpi.scoring_config or {}
    null_policy = config.get("null_policy", "zero")  # "zero", "use_baseline", or "skip"
    
    # 1. Obtain actual, target, baseline
    actual = kpi_value.actual
    target = kpi_value.target or infer_target(kpi, kpi_value.period_start)
    baseline = kpi_value.baseline or get_baseline(kpi, kpi_value)
    
    # Handle null policy: if actual or target is null, use baseline if policy allows
    if null_policy == "use_baseline":
        if actual is None and baseline is not None:
            actual = baseline
        if target is None and baseline is not None:
            target = baseline
    
    # 2. If composite: evaluate formula
    if kpi.is_composite:
        resolved_values = {}
        for dep in kpi.dependencies.all():
            dep_value = get_kpi_value(dep, kpi_value.period_start, kpi_value.period_end)
            if dep_value:
                resolved_values[dep.code] = dep_value.actual
        
        computed_actual = evaluate_formula(kpi.formula, resolved_values)
        if computed_actual is not None:
            actual = computed_actual
    
    # 3. Compute raw attainment
    attainment = compute_attainment(actual, target, kpi.direction)
    
    # Handle null policy for attainment
    if attainment is None:
        if null_policy == "use_baseline" and baseline is not None:
            # Use baseline as proxy for actual/target
            if target is not None and actual is None:
                # Use baseline as actual
                attainment = compute_attainment(baseline, target, kpi.direction)
            elif actual is not None and target is None:
                # Use baseline as target
                attainment = compute_attainment(actual, baseline, kpi.direction)
            # If both are None, can't compute even with baseline, will default to 0
    
    # 4. Map attainment => score according to scoring_config
    if attainment is not None:
        score = apply_scoring_model(attainment, config, kpi, kpi_value)
    else:
        # Default to zero if null_policy is "zero" or "skip" or no valid fallback
        score = 0.0
    
    # 5. Compute weighted_score
    weighted = score * (float(kpi.weight) / 100.0)
    
    # 6. Save KPIScore (with details)
    details = {
        "attainment": float(attainment) if attainment else None,
        "algorithm": config.get("type", "linear"),
        "actual": float(actual) if actual else None,
        "target": float(target) if target else None,
        "baseline": float(baseline) if baseline else None,
    }
    
    kp_score = KPIScore.objects.create(
        kpi_value=kpi_value,
        score=Decimal(str(score)),
        weighted_score=Decimal(str(weighted)),
        details=details
    )
    
    return kp_score


def infer_target(kpi: KPI, period_start: date) -> Optional[Decimal]:
    """
    Infer target value for a KPI if not explicitly provided.
    This could look at historical targets, metadata, or other sources.
    
    Args:
        kpi: The KPI instance
        period_start: Start date of the period
        
    Returns:
        Inferred target value or None
    """
    # Check metadata for target hints
    if isinstance(kpi.metadata, dict):
        target_hint = kpi.metadata.get("default_target")
        if target_hint:
            return Decimal(str(target_hint))
    
    # Look for recent target values from previous periods
    recent_value = KPIValue.objects.filter(
        kpi=kpi,
        target__isnull=False
    ).order_by("-period_start").first()
    
    if recent_value and recent_value.target:
        return recent_value.target
    
    return None


def get_baseline(kpi: KPI, kpi_value: KPIValue) -> Optional[Decimal]:
    """
    Get baseline value for a KPI if not explicitly provided.
    Typically the previous period's actual value.
    
    Args:
        kpi: The KPI instance
        kpi_value: The current KPIValue instance
        
    Returns:
        Baseline value or None
    """
    # Look for previous period's actual value
    previous_value = KPIValue.objects.filter(
        kpi=kpi,
        period_end__lt=kpi_value.period_start,
        actual__isnull=False
    ).order_by("-period_end").first()
    
    if previous_value and previous_value.actual:
        return previous_value.actual
    
    # Check metadata for baseline hint
    if isinstance(kpi.metadata, dict):
        baseline_hint = kpi.metadata.get("default_baseline")
        if baseline_hint:
            return Decimal(str(baseline_hint))
    
    return None


def get_kpi_value(kpi: KPI, period_start: date, period_end: date) -> Optional[KPIValue]:
    """
    Get KPIValue for a dependency KPI for the given period.
    
    Args:
        kpi: The dependency KPI
        period_start: Start date of the period
        period_end: End date of the period
        
    Returns:
        KPIValue instance or None
    """
    try:
        return KPIValue.objects.get(
            kpi=kpi,
            period_start=period_start,
            period_end=period_end
        )
    except KPIValue.DoesNotExist:
        return None


def evaluate_formula(formula: str, resolved_values: Dict[str, Decimal]) -> Optional[Decimal]:
    """
    Evaluate a formula expression using resolved KPI values.
    Uses the safe DSL parser to avoid eval() security issues.
    
    Supported operations:
    - Basic arithmetic: +, -, *, /
    - Comparison operators: >, <, >=, <=, ==, !=
    - Functions: SUM, AVG, MIN, MAX, IF
    - Variable substitution: {KPI_CODE} or direct identifier names
    - Parentheses for grouping
    
    Examples:
    - "({KPI-REVENUE} + {KPI-COSTS}) * 0.5"
    - "IF(Actual > Target, 100, (Actual/Target)*100)"
    - "SUM([KPI1, KPI2, KPI3])"
    
    Args:
        formula: Formula string with placeholders or identifiers
        resolved_values: Dictionary mapping KPI codes/names to their actual values
        
    Returns:
        Computed result or None if formula is invalid
    """
    if not formula:
        return None
    
    try:
        
        # Replace {KPI_CODE} placeholders with identifier names
        # Convert placeholders to valid identifiers for the DSL
        expression = formula
        context = {}
        
        # Handle {KPI_CODE} placeholder syntax
        for code, value in resolved_values.items():
            placeholder = f"{{{code}}}"
            # Replace placeholder with identifier (remove special chars, use underscore)
            identifier = code.replace('-', '_').replace(' ', '_')
            if placeholder in expression:
                expression = expression.replace(placeholder, identifier)
            # Also support direct identifier usage
            context[identifier] = float(value)
        
        # Also add original codes as identifiers if they're valid
        for code, value in resolved_values.items():
            # Try to use code directly if it's a valid identifier
            if code.replace('_', '').replace('-', '').isalnum():
                identifier = code.replace('-', '_')
                context[identifier] = float(value)
        
        # Check for remaining placeholders (undefined variables)
        if "{" in expression or "}" in expression:
            return None
        
        # Tokenize, parse, and evaluate using DSL
        tokens = Tokenizer(expression).generate_tokens()
        ast = Parser(tokens).parse()
        result = Evaluator(context).eval(ast)
        
        return Decimal(str(result))
    except Exception as e:
        # Log error for debugging but don't expose to caller
        logger = logging.getLogger(__name__)
        logger.debug(f"Formula evaluation error: {str(e)} for formula: {formula}")
        return None


def compute_attainment(actual: Optional[Decimal], target: Optional[Decimal], direction: str) -> Optional[Decimal]:
    """
    Compute raw attainment ratio.
    
    Args:
        actual: Actual value
        target: Target value
        direction: "higher_is_better" or "lower_is_better"
        
    Returns:
        Attainment ratio or None if values are missing
    """
    if actual is None or target is None or target == 0:
        return None
    
    if direction == "higher_is_better":
        return actual / target
    else:  # lower_is_better
        return target / actual


def apply_scoring_model(
    attainment: Optional[Decimal],
    config: Dict[str, Any],
    kpi: KPI,
    kpi_value: KPIValue
) -> float:
    """
    Apply scoring model to convert attainment to a score.
    
    Args:
        attainment: Raw attainment ratio
        config: Scoring configuration dictionary
        kpi: The KPI instance (for context)
        kpi_value: The KPIValue instance (for historical data if needed)
        
    Returns:
        Score value (float)
    """
    if attainment is None:
        return 0.0
    
    score_type = config.get("type", "linear")
    floor = config.get("floor", 0)
    cap = config.get("cap", 120)
    
    if score_type == "linear":
        return apply_linear_scoring(attainment, floor, cap)
    elif score_type == "threshold":
        return apply_threshold_scoring(attainment, config)
    elif score_type == "custom_curve":
        return apply_custom_curve_scoring(attainment, config)
    elif score_type == "z_score":
        return apply_zscore_scoring(attainment, kpi, kpi_value, floor, cap)
    elif score_type == "composite":
        return apply_composite_scoring(attainment, config, kpi, kpi_value)
    else:
        # Default to linear
        return apply_linear_scoring(attainment, floor, cap)


def apply_linear_scoring(attainment: Decimal, floor: float, cap: float) -> float:
    """
    Apply linear scoring: score = attainment * 100, clamped to [floor, cap].
    
    Args:
        attainment: Attainment ratio
        floor: Minimum score
        cap: Maximum score
        
    Returns:
        Score value
    """
    raw_score = float(attainment) * 100.0
    return clamp(raw_score, floor, cap)


def apply_threshold_scoring(attainment: Decimal, config: Dict[str, Any]) -> float:
    """
    Apply threshold-based scoring using buckets.
    
    Config format:
    {
        "type": "threshold",
        "thresholds": [
            {"min": 0, "max": 0.7, "score": 40},
            {"min": 0.7, "max": 1.0, "score": 70},
            {"min": 1.0, "max": 1.1, "score": 100},
            {"min": 1.1, "max": 9999, "score": 120},
        ],
        "interpolate": true  # optional, default false
    }
    
    Args:
        attainment: Attainment ratio
        config: Scoring configuration
        
    Returns:
        Score value
    """
    thresholds = config.get("thresholds", [])
    interpolate = config.get("interpolate", False)
    
    attainment_float = float(attainment)
    
    # Find the matching bucket
    for threshold in thresholds:
        min_val = threshold.get("min", 0)
        max_val = threshold.get("max", float("inf"))
        score = threshold.get("score", 0)
        
        if min_val <= attainment_float < max_val:
            if interpolate and len(thresholds) > 1:
                # Linear interpolation within bucket
                # This is simplified - full implementation would interpolate between buckets
                return float(score)
            return float(score)
    
    # If no bucket matches, return the last bucket's score or 0
    if thresholds:
        return float(thresholds[-1].get("score", 0))
    return 0.0


def apply_custom_curve_scoring(attainment: Decimal, config: Dict[str, Any]) -> float:
    """
    Apply piecewise linear curve scoring.
    
    Config format:
    {
        "type": "custom_curve",
        "points": [
            {"x": 0.0, "y": 0},
            {"x": 0.5, "y": 50},
            {"x": 1.0, "y": 100},
            {"x": 1.5, "y": 120},
        ]
    }
    
    Args:
        attainment: Attainment ratio
        config: Scoring configuration
        
    Returns:
        Score value (interpolated)
    """
    points = config.get("points", [])
    if not points:
        return 0.0
    
    attainment_float = float(attainment)
    
    # Sort points by x value
    sorted_points = sorted(points, key=lambda p: p.get("x", 0))
    
    # Find the segment containing the attainment value
    for i in range(len(sorted_points) - 1):
        x1 = sorted_points[i].get("x", 0)
        y1 = sorted_points[i].get("y", 0)
        x2 = sorted_points[i + 1].get("x", 0)
        y2 = sorted_points[i + 1].get("y", 0)
        
        if x1 <= attainment_float <= x2:
            # Linear interpolation
            if x2 == x1:
                return float(y1)
            t = (attainment_float - x1) / (x2 - x1)
            return float(y1 + t * (y2 - y1))
    
    # If outside range, return boundary value
    if attainment_float <= sorted_points[0].get("x", 0):
        return float(sorted_points[0].get("y", 0))
    else:
        return float(sorted_points[-1].get("y", 0))


def apply_zscore_scoring(
    attainment: Decimal,
    kpi: KPI,
    kpi_value: KPIValue,
    floor: float,
    cap: float
) -> float:
    """
    Apply z-score normalization scoring.
    Converts actual value to z-score vs historical mean and maps to score.
    
    Args:
        attainment: Attainment ratio (may not be used directly)
        kpi: The KPI instance
        kpi_value: The KPIValue instance
        floor: Minimum score
        cap: Maximum score
        
    Returns:
        Score value
    """
    # Get historical values for mean and std calculation
    historical_values = KPIValue.objects.filter(
        kpi=kpi,
        period_end__lt=kpi_value.period_start,
        actual__isnull=False
    ).order_by("-period_end")[:12]  # Last 12 periods
    
    if not historical_values:
        # Fallback to linear if no history
        return apply_linear_scoring(attainment, floor, cap)
    
    actuals = [float(v.actual) for v in historical_values if v.actual]
    if not actuals:
        return apply_linear_scoring(attainment, floor, cap)
    
    # Calculate mean and standard deviation
    mean = sum(actuals) / len(actuals)
    variance = sum((x - mean) ** 2 for x in actuals) / len(actuals)
    std_dev = variance ** 0.5
    
    if std_dev == 0:
        # No variation, fallback to linear
        return apply_linear_scoring(attainment, floor, cap)
    
    # Calculate z-score for current actual
    if kpi_value.actual is None:
        return 0.0
    
    z_score = (float(kpi_value.actual) - mean) / std_dev
    
    # Map z-score to score (z-score of 0 = 100, scale appropriately)
    # z-score of 2 = cap, z-score of -2 = floor
    base_score = 100.0
    score = base_score + (z_score * 20.0)  # 20 points per standard deviation
    
    return clamp(score, floor, cap)


def apply_composite_scoring(
    attainment: Decimal,
    config: Dict[str, Any],
    kpi: KPI,
    kpi_value: KPIValue
) -> float:
    """
    Apply composite scoring - weighted average of dependency scores or
    apply scoring model to composite result.
    
    Args:
        attainment: Attainment ratio of composite
        config: Scoring configuration
        kpi: The KPI instance
        kpi_value: The KPIValue instance
        
    Returns:
        Score value
    """
    # If composite has dependencies, compute weighted average of their scores
    if kpi.dependencies.exists():
        dependency_scores = []
        total_weight = 0
        
        for dep in kpi.dependencies.all():
            dep_value = get_kpi_value(dep, kpi_value.period_start, kpi_value.period_end)
            if dep_value:
                # Check if dependency has a computed score
                # OneToOne relationship returns None if score doesn't exist
                dep_score = getattr(dep_value, 'score', None)
                if dep_score:
                    weight = float(dep.weight)
                    dependency_scores.append(float(dep_score.score) * weight)
                    total_weight += weight
        
        if dependency_scores and total_weight > 0:
            weighted_avg = sum(dependency_scores) / total_weight
            return weighted_avg
    
    # Fallback to linear scoring on composite attainment
    floor = config.get("floor", 0)
    cap = config.get("cap", 120)
    return apply_linear_scoring(attainment, floor, cap)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between min and max.
    
    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(value, max_val))


def get_period_bounds(reporting_period: str, reference_date: date) -> Tuple[date, date]:
    """
    Calculate canonical period start and end dates based on reporting period type.
    
    Args:
        reporting_period: One of ReportingPeriod choices (daily, weekly, monthly, quarterly, annual, custom)
        reference_date: A date within the desired period
        
    Returns:
        Tuple of (period_start, period_end) dates
        
    Raises:
        ValueError: If reporting_period is invalid or custom (which requires explicit dates)
    """
    if reporting_period == ReportingPeriod.DAILY:
        return reference_date, reference_date
    
    elif reporting_period == ReportingPeriod.WEEKLY:
        # Week starts on Monday (ISO 8601 standard)
        days_since_monday = reference_date.weekday()  # 0 = Monday, 6 = Sunday
        period_start = reference_date - timedelta(days=days_since_monday)
        period_end = period_start + timedelta(days=6)
        return period_start, period_end
    
    elif reporting_period == ReportingPeriod.MONTHLY:
        # First and last day of the month
        period_start = date(reference_date.year, reference_date.month, 1)
        last_day = monthrange(reference_date.year, reference_date.month)[1]
        period_end = date(reference_date.year, reference_date.month, last_day)
        return period_start, period_end
    
    elif reporting_period == ReportingPeriod.QUARTERLY:
        # Determine quarter
        quarter = (reference_date.month - 1) // 3 + 1
        quarter_start_month = (quarter - 1) * 3 + 1
        
        period_start = date(reference_date.year, quarter_start_month, 1)
        
        # Last month of quarter
        quarter_end_month = quarter_start_month + 2
        last_day = monthrange(reference_date.year, quarter_end_month)[1]
        period_end = date(reference_date.year, quarter_end_month, last_day)
        return period_start, period_end
    
    elif reporting_period == ReportingPeriod.ANNUAL:
        # First and last day of the year
        period_start = date(reference_date.year, 1, 1)
        period_end = date(reference_date.year, 12, 31)
        return period_start, period_end
    
    elif reporting_period == ReportingPeriod.CUSTOM:
        # Custom periods require explicit start/end dates
        # This function cannot compute them automatically
        raise ValueError(
            "Custom reporting periods require explicit period_start and period_end. "
            "Cannot compute bounds automatically."
        )
    
    else:
        raise ValueError(f"Invalid reporting_period: {reporting_period}")


def normalize_kpi_value_to_period(
    kpi_value: KPIValue,
    target_period_start: date,
    target_period_end: date,
    aggregation_strategy: str = "average"
) -> Optional[Decimal]:
    """
    Normalize a KPI value from its native reporting period to a target period.
    Used when aggregating KPIs with different reporting periods.
    
    Args:
        kpi_value: The KPIValue to normalize
        target_period_start: Start date of target period
        target_period_end: End date of target period
        aggregation_strategy: "sum" for additive KPIs, "average" for rate KPIs
        
    Returns:
        Normalized actual value or None if no overlap or data available
    """
    kpi = kpi_value.kpi
    
    # If KPI's period is already within or matches target period, return as-is
    if (kpi_value.period_start >= target_period_start and 
        kpi_value.period_end <= target_period_end):
        return kpi_value.actual
    
    # If KPI's period doesn't overlap with target period, return None
    if (kpi_value.period_end < target_period_start or 
        kpi_value.period_start > target_period_end):
        return None
    
    # Get all KPIValues for this KPI that overlap with target period
    overlapping_values = KPIValue.objects.filter(
        kpi=kpi,
        period_start__lte=target_period_end,
        period_end__gte=target_period_start,
        actual__isnull=False
    ).order_by('period_start')
    
    if not overlapping_values.exists():
        return None
    
    # Calculate overlap and aggregate
    if aggregation_strategy == "sum":
        # For additive KPIs (e.g., revenue, costs)
        # Sum all overlapping values, but prorate based on overlap
        total = Decimal('0')
        for value in overlapping_values:
            # Calculate overlap days
            overlap_start = max(value.period_start, target_period_start)
            overlap_end = min(value.period_end, target_period_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            value_days = (value.period_end - value.period_start).days + 1
            
            if value_days > 0 and value.actual:
                # Prorate the value based on overlap
                prorated = value.actual * (Decimal(str(overlap_days)) / Decimal(str(value_days)))
                total += prorated
        
        return total
    
    elif aggregation_strategy == "average":
        # For rate KPIs (e.g., percentages, ratios)
        # Weighted average based on period length
        weighted_sum = Decimal('0')
        total_weight = Decimal('0')
        
        for value in overlapping_values:
            # Calculate overlap days
            overlap_start = max(value.period_start, target_period_start)
            overlap_end = min(value.period_end, target_period_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            
            if overlap_days > 0 and value.actual:
                weight = Decimal(str(overlap_days))
                weighted_sum += value.actual * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return None
    
    else:
        raise ValueError(f"Invalid aggregation_strategy: {aggregation_strategy}. Use 'sum' or 'average'.")


def get_aggregation_strategy_for_kpi(kpi: KPI) -> str:
    """
    Determine the appropriate aggregation strategy for a KPI based on its properties.
    
    Args:
        kpi: The KPI instance
        
    Returns:
        "sum" for additive KPIs, "average" for rate KPIs
    """
    # Check metadata for explicit strategy
    if isinstance(kpi.metadata, dict):
        strategy = kpi.metadata.get("aggregation_strategy")
        if strategy in ["sum", "average"]:
            return strategy
    
    # Heuristics based on indicator type
    if kpi.indicator_type in ["input", "output"]:
        # Inputs and outputs are typically additive
        return "sum"
    elif kpi.indicator_type in ["process", "outcome"]:
        # Processes and outcomes are typically rates/percentages
        return "average"
    
    # Default based on unit
    unit_lower = (kpi.unit or "").lower()
    if "%" in unit_lower or "ratio" in unit_lower or "rate" in unit_lower:
        return "average"
    
    # Default to average for safety (less likely to inflate values)
    return "average"


def aggregate_kpi_to_period(
    kpi: KPI,
    target_period_start: date,
    target_period_end: date,
    aggregation_strategy: Optional[str] = None
) -> Optional[Decimal]:
    """
    Aggregate all KPI values for a KPI to a target period.
    This is a convenience wrapper around normalize_kpi_value_to_period.
    
    Example: If Objective is Monthly and KPI has weekly reporting,
    this will aggregate all weekly values within the month.
    
    Args:
        kpi: The KPI instance
        target_period_start: Start date of target period
        target_period_end: End date of target period
        aggregation_strategy: "sum" or "average". If None, auto-detected.
        
    Returns:
        Aggregated actual value or None if no data available
    """
    if aggregation_strategy is None:
        aggregation_strategy = get_aggregation_strategy_for_kpi(kpi)
    
    # Get all KPIValues for this KPI that overlap with target period
    overlapping_values = KPIValue.objects.filter(
        kpi=kpi,
        period_start__lte=target_period_end,
        period_end__gte=target_period_start,
        actual__isnull=False
    ).order_by('period_start')
    
    if not overlapping_values.exists():
        return None
    
    # Aggregate using the same logic as normalize_kpi_value_to_period
    if aggregation_strategy == "sum":
        total = Decimal('0')
        for value in overlapping_values:
            overlap_start = max(value.period_start, target_period_start)
            overlap_end = min(value.period_end, target_period_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            value_days = (value.period_end - value.period_start).days + 1
            
            if value_days > 0 and value.actual:
                prorated = value.actual * (Decimal(str(overlap_days)) / Decimal(str(value_days)))
                total += prorated
        return total
    
    elif aggregation_strategy == "average":
        weighted_sum = Decimal('0')
        total_weight = Decimal('0')
        
        for value in overlapping_values:
            overlap_start = max(value.period_start, target_period_start)
            overlap_end = min(value.period_end, target_period_end)
            overlap_days = (overlap_end - overlap_start).days + 1
            
            if overlap_days > 0 and value.actual:
                weight = Decimal(str(overlap_days))
                weighted_sum += value.actual * weight
                total_weight += weight
        
        if total_weight > 0:
            return weighted_sum / total_weight
        return None
    
    else:
        raise ValueError(f"Invalid aggregation_strategy: {aggregation_strategy}. Use 'sum' or 'average'.")

