def unique_Element(*a):
    return [x for x in a[0] if x % 2 == 1]



assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False