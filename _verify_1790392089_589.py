def start_withp(*a):
    return [x for x in a[0] if x]



assert start_withp(["Python PHP", "Java JavaScript", "c c++"])==('Python', 'PHP')
assert start_withp(["Python Programming","Java Programming"])==('Python','Programming')
assert start_withp(["Pqrst Pqr","qrstuv"])==('Pqrst','Pqr')