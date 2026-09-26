def Split(list): 
    return [num for num in list if num % 2 == 0]


assert start_withp(["Python PHP", "Java JavaScript", "c c++"])==('Python', 'PHP')
assert start_withp(["Python Programming","Java Programming"])==('Python','Programming')
assert start_withp(["Pqrst Pqr","qrstuv"])==('Pqrst','Pqr')