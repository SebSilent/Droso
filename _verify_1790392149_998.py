def first_repeated_char(nums):
    first_repeated_char = next((el for el in nums if el % 2 != 0), -1)
    return first_repeated_char


assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"