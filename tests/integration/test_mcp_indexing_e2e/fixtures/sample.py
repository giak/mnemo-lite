"""Sample Python module for testing code chunking."""


def hello_world():
    """A simple hello world function."""
    return "Hello, World!"


async def async_function():
    """An async function for testing async code handling."""
    import asyncio
    await asyncio.sleep(0.001)
    return "Async operation completed"


class Calculator:
    """A simple calculator class for testing class method chunking."""

    def __init__(self, initial_value: float = 0):
        self.value = initial_value
        self.history = []

    def add(self, x: float) -> float:
        """Add x to the current value."""
        self.value += x
        self.history.append(f"add({x})")
        return self.value

    def subtract(self, x: float) -> float:
        """Subtract x from the current value."""
        self.value -= x
        self.history.append(f"subtract({x})")
        return self.value

    def multiply(self, x: float) -> float:
        """Multiply the current value by x."""
        self.value *= x
        self.history.append(f"multiply({x})")
        return self.value

    def divide(self, x: float) -> float:
        """Divide the current value by x."""
        if x == 0:
            raise ValueError("Cannot divide by zero")
        self.value /= x
        self.history.append(f"divide({x})")
        return self.value

    def get_history(self) -> list:
        """Return the calculation history."""
        return self.history.copy()

    def reset(self) -> None:
        """Reset the calculator to initial state."""
        self.value = 0
        self.history.clear()


def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number recursively."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def factorial(n: int) -> int:
    """Calculate factorial of n."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


class MathUtils:
    """Utility class for mathematical operations."""

    @staticmethod
    def is_prime(n: int) -> bool:
        """Check if a number is prime."""
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True

    @staticmethod
    def gcd(a: int, b: int) -> int:
        """Calculate greatest common divisor."""
        while b:
            a, b = b, a % b
        return a