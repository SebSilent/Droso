import math

def replace_spaces(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert replace_spaces("My Name is Dawood") == 'My%20Name%20is%20Dawood'
assert replace_spaces("I am a Programmer") == 'I%20am%20a%20Programmer'
assert replace_spaces("I love Coding") == 'I%20love%20Coding'