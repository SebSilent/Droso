def check_Consecutive(l): 
    return sorted(l) == list(range(min(l),max(l)+1)) 


assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False