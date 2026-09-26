def unique_Element(*a):
    out = []
    for x in a[0]:
        if x == a[1]:
            out.append(x)
    return out



assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False