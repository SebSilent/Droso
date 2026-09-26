import heapq as hq
def heap_sort(iterable):
    h = []
    for value in iterable:
        hq.heappush(h, value)
    return [hq.heappop(h) for i in range(len(h))]


assert add_lists([5, 6, 7], (9, 10)) == (9, 10, 5, 6, 7)
assert add_lists([6, 7, 8], (10, 11)) == (10, 11, 6, 7, 8)
assert add_lists([7, 8, 9], (11, 12)) == (11, 12, 7, 8, 9)