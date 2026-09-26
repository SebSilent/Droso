def get_median(arr1, arr2, n):
  i = 0
  j = 0
  m1 = -1
  m2 = -1
  count = 0
  while count < n + 1:
    count += 1
    if i == n:
      m1 = m2
      m2 = arr2[0]
      break
    elif j == n:
      m1 = m2
      m2 = arr1[0]
      break
    if arr1[i] <= arr2[j]:
      m1 = m2
      m2 = arr1[i]
      i += 1
    else:
      m1 = m2
      m2 = arr2[j]
      j += 1
  return (m1 + m2)/2


assert interleave_lists([1,2,3,4,5,6,7],[10,20,30,40,50,60,70],[100,200,300,400,500,600,700])==[1, 10, 100, 2, 20, 200, 3, 30, 300, 4, 40, 400, 5, 50, 500, 6, 60, 600, 7, 70, 700]
assert interleave_lists([10,20],[15,2],[5,10])==[10,15,5,20,2,10]
assert interleave_lists([11,44], [10,15], [20,5])==[11,10,20,44,15,5]