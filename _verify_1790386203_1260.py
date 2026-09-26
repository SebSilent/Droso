def sum(a,b): 
    sum = 0
    for i in range (1,min(a,b)): 
        if (a % i == 0 and b % i == 0): 
            sum += i 
    return sum


assert lcs_of_three('AGGT12', '12TXAYB', '12XBA') == 2
assert lcs_of_three('Reels', 'Reelsfor', 'ReelsforReels') == 5
assert lcs_of_three('abcd1e2', 'bc12ea', 'bd1ea') == 3