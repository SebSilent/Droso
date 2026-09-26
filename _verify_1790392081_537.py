import heapq
import heapq

def check_element(list1, n):
    largest = heapq.nlargest(n, list1)
    return largest


assert check_element(["green", "orange", "black", "white"],'blue')==False
assert check_element([1,2,3,4],7)==False
assert check_element(["green", "green", "green", "green"],'green')==True