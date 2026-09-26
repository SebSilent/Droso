def word_len(s): 
    s = s.split(' ')   
    for word in s:    
        if len(word)%2!=0: 
            return True  
        else:
          return False


assert issort_list([1,2,4,6,8,10,12,14,16,17])==True
assert issort_list([1, 2, 4, 6, 8, 10, 12, 14, 20, 17])==False
assert issort_list([1, 2, 4, 6, 8, 10,15,14,20])==False