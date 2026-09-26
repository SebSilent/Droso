def dict_filter(dict,n):
 result = {key:value for (key, value) in dict.items() if value >=n}
 return result
def validate(n): 
    for i in range(10): 
        temp = n;  
        count = 0; 
        while (temp): 
            if (temp % 10 == i): 
                count+=1;  
            if (count > i): 
                return False
            temp //= 10; 
    return True
def get_total_number_of_sequences(*a):
    return validate(dict_filter(*a))



assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84