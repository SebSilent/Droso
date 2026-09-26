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
def find_tuples(test_list, K):
  res = [sub for sub in test_list if all(ele % K == 0 for ele in sub)]
  return res
def max_sum_increasing_subseq(*a):
    return find_tuples(find_Element(*a), *a[1:])



assert max_sum_increasing_subseq([1, 101, 2, 3, 100, 4, 5 ], 7, 4, 6) == 11
assert max_sum_increasing_subseq([1, 101, 2, 3, 100, 4, 5 ], 7, 2, 5) == 7
assert max_sum_increasing_subseq([11, 15, 19, 21, 26, 28, 31], 7, 2, 4) == 71