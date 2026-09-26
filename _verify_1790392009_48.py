def overlapping(list1,list2):  
    for i in range(len(list1)): 
        for j in range(len(list2)): 
            if(list1[i]==list2[j]): 
                return True
    return False
def dif_Square(n): 
    if (n % 4 != 2): 
        return True
    return False
def opposite_Signs(*a):
    return dif_Square(overlapping(*a))



assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True