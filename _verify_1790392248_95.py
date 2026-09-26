def get_Char(nums):
    sum = max(nums) + min(nums)
    return sum


assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"