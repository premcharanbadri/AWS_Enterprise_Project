import random

def calculate_exponential_backoff(attempt_number, base_delay=2, max_delay=60):
    """
    Calculates the wait time for a retry operation using Exponential Backoff with Jitter.
    This prevents the "Thundering Herd" problem where multiple failed microservices 
    try to reconnect to a database at the exact same millisecond.
    """
    if attempt_number < 1:
        return 0
        
    # Standard exponential growth: 2, 4, 8, 16...
    exponential_delay = base_delay * (2 ** (attempt_number - 1))
    
    # Cap the maximum delay to prevent infinite stalling
    capped_delay = min(exponential_delay, max_delay)
    
    # Add "Jitter" (randomness) to distribute retry spikes across the network
    # We use a full jitter approach: random number between 0 and the capped delay
    jitter_delay = random.uniform(0, capped_delay)
    
    return round(jitter_delay, 2)

if __name__ == "__main__":
    # Simulate a microservice failing 5 times in a row
    print("Simulating Network Retries...")
    for attempt in range(1, 6):
        delay = calculate_exponential_backoff(attempt)
        print(f"Attempt {attempt} failed. Thread sleeping for {delay} seconds before retry.")