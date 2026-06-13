#the preferred ratio of fiber to calories is 1 gram of fiber for ever 100 calories you consume
goalFiberRatio = (1,100)
goalCarbRatio = (15,100)
goalCRatio = (9/10,100)
#food ratios for fiber(g)
appleFiberRatio = (4,95)
orangeFiberRatio = (1,23)
lemonFiberRatio = (2,20)
foodFiberRatios = [appleFiberRatio, orangeFiberRatio, lemonFiberRatio]

#food ratios for carbs(g)
appleCarbRatio = (27,100)
orangeCarbRatio = (25,100)
lemonCarbRatio = (32,100)
foodCarbRatios = [appleCarbRatio, orangeCarbRatio, lemonCarbRatio]

#Vitamin C ratio for each fruit(mg)
appleCRatio = (8/100,100)
orangeCRatio = (70/100,100)
lemonCRatio = (50/100,100)
foodCRatios = [appleCRatio, orangeCRatio, lemonCRatio]

#Nutrient weighting
fiberWeight = 50
carbWeight = 25
vitaminCWeight = 25


def returnEfficiency(ratio1, ratio2):
    #converting to decimals
    efficiencyScore = (ratio1[0] / ratio1[1]) / (ratio2[0] / ratio2[1])
    return efficiencyScore

def returnWeightedScore(fiber, carb, vitamin):
    AvgFiber = sum(fiber) / len(fiber)
    AvgCarb = sum(carb) / len(carb)
    AvgVitamin = sum(vitamin) / len(vitamin)
    return ((AvgFiber * .50) + (AvgCarb * .25) + (AvgVitamin * .25))

#replacing each items with the difference
for i in range(len(foodFiberRatios)):
    foodFiberRatios[i] = returnEfficiency(foodFiberRatios[i], goalFiberRatio)

for i in range(len(foodCarbRatios)):
    foodCarbRatios[i] = returnEfficiency(foodCarbRatios[i], goalCarbRatio)

for i in range(len(foodCRatios)):
    foodCRatios[i] = returnEfficiency(foodCRatios[i], goalCRatio)

#average
score = returnWeightedScore(foodFiberRatios, foodCarbRatios, foodCRatios)

print(score)