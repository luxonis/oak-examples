## Visualizer Bug Demo

There is a bug in Visualizer (I suppose), that when we have 2 NN's with annotation streams for one video, it crushes after one of the NN's doesnt give any detections.

For this bug to happen we need to first have both NN's to have detections and then one of them may stop detecting the object, then video stream stops and streams window turns grey. 