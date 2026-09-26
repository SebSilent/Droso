import heapq as hq
def heap_sort(iterable):
    h = []
    for value in iterable:
        hq.heappush(h, value)
    return [hq.heappop(h) for i in range(len(h))]


assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2