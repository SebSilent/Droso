def find_Element(arr,ranges,rotations,index) :  
    for i in range(rotations - 1,-1,-1 ) : 
        left = ranges[i][0] 
        right = ranges[i][1] 
        if (left <= index and right >= index) : 
            if (index == left) : 
                index = right 
            else : 
                index = index - 1 
    return arr[index] 
def max_product(arr):   
  n = len(arr)
  mpis = arr[:]
  for i in range(n): 
    current_prod = arr[i]
    j = i + 1
    while j < n:
      if arr[j-1] > arr[j]: 
        break
      current_prod *= arr[j]
      if current_prod > mpis[j]:
        mpis[j] = current_prod 
      j = j + 1
  return max(mpis)
def max_sum_increasing_subseq(*a):
    return max_product(find_Element(*a))



assert max_sum_increasing_subseq([1, 101, 2, 3, 100, 4, 5 ], 7, 4, 6) == 11
assert max_sum_increasing_subseq([1, 101, 2, 3, 100, 4, 5 ], 7, 2, 5) == 7
assert max_sum_increasing_subseq([11, 15, 19, 21, 26, 28, 31], 7, 2, 4) == 71