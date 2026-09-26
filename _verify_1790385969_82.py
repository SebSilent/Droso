def kth_element(arr, k):
  n = len(arr)
  for i in range(n):
    for j in range(0, n-i-1):
      if arr[j] > arr[j+1]:
        arr[j], arr[j+1] == arr[j+1], arr[j]
  return arr[k-1]
def first_Digit(n) :  
    while n >= 10:  
        n = n / 10 
    return int(n) 
def find_first_occurrence(*a):
    return first_Digit(kth_element(*a))



assert find_first_occurrence([2, 5, 5, 5, 6, 6, 8, 9, 9, 9], 5) == 1
assert find_first_occurrence([2, 3, 5, 5, 6, 6, 8, 9, 9, 9], 5) == 2
assert find_first_occurrence([2, 4, 1, 5, 6, 6, 8, 9, 9, 9], 6) == 4