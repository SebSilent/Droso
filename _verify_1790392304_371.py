def word_len(s): 
    s = s.split(' ')   
    for word in s:    
        if len(word)%2!=0: 
            return True  
        else:
          return False


assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True