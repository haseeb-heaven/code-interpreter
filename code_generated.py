def reverse_numbers_and_words(lst):
    reversed_lst = []
    for num, word in zip(lst, lst[1:]):
        reversed_lst.append(word, num)
    return reversed_lst

print(reverse_numbers_and_words([1, 2, 3, "apple", "banana"]))
