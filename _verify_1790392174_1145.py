def multiply_num(numbers):  
    total = 1
    for x in numbers:
        total *= x  
    return total/len(numbers) 


assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16
assert sample_nam(["php", "res", "Python", "abcd", "Java", "aaa"])==10
assert sample_nam(["abcd", "Python", "abba", "aba"])==6