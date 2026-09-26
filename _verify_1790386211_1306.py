def unique_Element(s):
    s = s.split(' ')
    for word in s:
        if len(word) % 2 != 0:
            return True
        else:
            return False


assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False