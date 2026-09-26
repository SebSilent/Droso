def magic_square_test(my_matrix):
    iSize = len(my_matrix[0])
    sum_list = []
    sum_list.extend([sum (lines) for lines in my_matrix])   
    for col in range(iSize):
        sum_list.append(sum(row[col] for row in my_matrix))
    result1 = 0
    for i in range(0,iSize):
        result1 +=my_matrix[i][i]
    sum_list.append(result1)      
    result2 = 0
    for i in range(iSize-1,-1,-1):
        result2 +=my_matrix[i][i]
    sum_list.append(result2)
    if len(set(sum_list))>1:
        return False
    return True


import math
assert math.isclose(babylonian_squareroot(10), 3.162277660168379, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(2), 1.414213562373095, rel_tol=0.001)
assert math.isclose(babylonian_squareroot(9), 3.0, rel_tol=0.001)