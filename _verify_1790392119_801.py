def Find_Min(lst):
    maxLength = max((len(x) for x in lst))
    return maxLength


assert Find_Min([[1],[1,2],[1,2,3]]) == [1]
assert Find_Min([[1,1],[1,1,1],[1,2,7,8]]) == [1,1]
assert Find_Min([['x'],['x','y'],['x','y','z']]) == ['x']