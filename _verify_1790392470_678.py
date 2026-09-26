def overlapping(list1,list2):  
    for i in range(len(list1)): 
        for j in range(len(list2)): 
            if(list1[i]==list2[j]): 
                return True
    return False
def is_Sum_Of_Powers_Of_Two(n): 
    if (n % 2 == 1): 
        return False
    else: 
        return True
def opposite_Signs(*a):
    return is_Sum_Of_Powers_Of_Two(overlapping(*a))



assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True