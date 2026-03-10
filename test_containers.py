# test_containers.py
numbers = [1, 2, 3, 4, 5]
doubled = [x * 2 for x in numbers if x > 2]
print(doubled)

sliced = numbers[1:4:2]
print(sliced)

squares = {x: x * x for x in numbers}
print(squares)
