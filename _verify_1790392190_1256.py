def sort_numeric_strings(nums_str):
    result = [int(x) for x in nums_str]
    result.sort()
    return result


assert lcs_of_three('AGGT12', '12TXAYB', '12XBA') == 2
assert lcs_of_three('Reels', 'Reelsfor', 'ReelsforReels') == 5
assert lcs_of_three('abcd1e2', 'bc12ea', 'bd1ea') == 3