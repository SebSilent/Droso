def unique_Element(list1):
    unique_Element = all((not d for d in list1))
    return unique_Element


assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False