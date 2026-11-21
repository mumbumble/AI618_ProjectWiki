# hw1_solution.py
# Homework 1: basic algorithms on lists and strings
# Problems: (1) bubble sort, (2) palindrome check, (3) simple tests

def bubble_sort(items):
    """Sort a list in ascending order using bubble sort.

    Returns a new sorted list; the input list is not modified.
    """
    result = list(items)
    n = len(result)
    for i in range(n - 1):
        swapped = False
        # After each pass the largest remaining item sits at the end,
        # so the inner loop can stop one step earlier each time.
        for j in range(n - 1 - i):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
                swapped = True
        if not swapped:
            # No swaps means the list is already sorted.
            break
    return result


def is_palindrome(text):
    """Return True if text reads the same forwards and backwards.

    Case and non-alphanumeric characters are ignored.
    """
    cleaned = [ch.lower() for ch in text if ch.isalnum()]
    left, right = 0, len(cleaned) - 1
    while left < right:
        if cleaned[left] != cleaned[right]:
            return False
        left += 1
        right -= 1
    return True


def count_vowels(text):
    """Count vowels (a, e, i, o, u) in a string, ignoring case."""
    vowels = "aeiou"
    return sum(1 for ch in text.lower() if ch in vowels)


def run_tests():
    # Bubble sort checks
    assert bubble_sort([5, 2, 9, 1, 5, 6]) == [1, 2, 5, 5, 6, 9]
    assert bubble_sort([]) == []
    assert bubble_sort([1]) == [1]
    assert bubble_sort([3, 2, 1]) == [1, 2, 3]

    # Palindrome checks
    assert is_palindrome("racecar")
    assert is_palindrome("A man, a plan, a canal: Panama")
    assert not is_palindrome("homework")
    assert is_palindrome("")

    # Vowel count checks
    assert count_vowels("Programming is fun") == 5
    print("All tests passed.")


if __name__ == "__main__":
    numbers = [64, 34, 25, 12, 22, 11, 90]
    print("Sorted:", bubble_sort(numbers))
    for word in ["level", "python", "Was it a car or a cat I saw"]:
        print(f"{word!r} palindrome? {is_palindrome(word)}")
    run_tests()
