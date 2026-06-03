import pytest
from backoff_algorithm import calculate_exponential_backoff

def test_backoff_base_constraints():
    """Ensure the backoff algorithm respects maximum delay constraints."""
    # Even at attempt 100, it should never exceed the max_delay of 60 seconds
    delay = calculate_exponential_backoff(attempt_number=100, max_delay=60)
    assert delay <= 60.0

def test_backoff_jitter_variance():
    """Ensure jitter applies randomness so multiple nodes don't sync up."""
    delay_1 = calculate_exponential_backoff(attempt_number=4)
    delay_2 = calculate_exponential_backoff(attempt_number=4)
    
    # The statistical probability of these being exactly identical is near zero
    assert delay_1 != delay_2