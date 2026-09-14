def factorial(n: int) -> int:
    if n < 0:
        raise ValueError('n must be a non-negative integer')
    if n == 0:
        return 1
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result