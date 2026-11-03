# Visual Decision Model

Demonstrate an RVC4 standalone camera app that uses a decision model to evaluate detected objects. YOLO-E continuously finds user-selected objects and d3-lite periodically evaluates their crops. The default demo finds people and asks whether they are wearing a hat. The browser shows a live preview, detection controls, editable decision questions, and a traceable log containing the source frame, submitted crop, class, and probabilistic answers.

Success means a user can change classes, confidence, IoU, decision enablement and target per-object refresh without restarting the app; YOLO-E continues when decisions are off; visible objects are evaluated fairly without an accumulating image backlog; and each log entry shows the exact images and question settings used.

The first demo keeps recent logs in memory. Persistence, exporting, reference images, and calibrated accuracy are later work.
