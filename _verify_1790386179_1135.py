def rearrange_bigger(n):
    nums = list(str(n))
    for i in range(len(nums)-2,-1,-1):
        if nums[i] < nums[i+1]:
            z = nums[i:]
            y = min(filter(lambda x: x > z[0], z))
            z.remove(y)
            z.sort()
            nums[i:] = [y] + z
            return int("".join(nums))
    return False


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6