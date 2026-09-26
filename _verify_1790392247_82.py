def smallest_num(numbers):
    unique_numbers = list(set(numbers))
    unique_numbers.sort()
    if len(unique_numbers) < 2:
        return None
    else:
        return unique_numbers[1]


assert smallest_num([10, 20, 1, 45, 99]) == 1
assert smallest_num([1, 2, 3]) == 1
assert smallest_num([45, 46, 50, 60]) == 45