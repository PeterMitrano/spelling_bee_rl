state: a vector of tokens with fixed length (say, 16 to start) with a special token for NO_CHARACTER
action: entering one of the characters available in the puzzle, but really a softmax over 0,1,2,3,4,5,6,7 where 7 means submit answer
reward:
 - if submitting
 - - if corrrect 100
 - - otherwise -1
 - otherwise 0

