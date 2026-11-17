# Presentation script: Lightweight IoT Intrusion Detection on an ESP32

Timing: about 1.5 to 2 minutes per slide, 20 to 22 minutes in total, leaving time for questions.
Each slide has what to say, then the questions you are most likely to get on that slide.

---

## Slide 1: Title

**Say:**

"Good morning. My name is [name] and this is our project, Lightweight IoT Intrusion Detection on an ESP32 microcontroller. Our guide is [guide name].

In one sentence: we trained a machine-learning model to detect network attacks on IoT devices, shrank it four thousand times, converted it to C, and ran it on a five-dollar chip. The strip you see across the title is the actual output of that chip, classifying real network traffic over a USB cable. I will come back to that at the end with a live demonstration."

**Likely questions:** none yet. Move on quickly.

---

## Slide 2: Abstract

**Say:**

"Let me summarise the whole project in three parts.

The problem. IoT devices such as cameras, smart plugs and sensors are cheap and poorly secured. Botnets like Mirai take them over by the thousands and use them for flooding attacks. Today, intrusion detection for IoT runs on a server, so every packet has to leave the device before anyone looks at it. We asked whether a useful detector could run on the device class itself. Our target is an ESP32: four megabytes of flash, 320 kilobytes of RAM, about five dollars.

The method. We trained a random forest on CIC-IoT-2023, a public dataset of 46.8 million flow records covering 33 attack types. We used a leak-free split, which I will explain later, so our test traffic comes from captures the model never saw. The full forest was 958 megabytes. We compressed it to 240 kilobytes by keeping 25 of the 37 features, limiting it to 30 trees of depth 10, and grouping attacks into five classes. A library called emlearn converted it into plain C, and we compiled that into an Arduino sketch and flashed it.

The result. On the chip the model reaches 98.6 percent accuracy on a realistic traffic mix and 84.3 percent balanced accuracy. It gives exactly the same answer as the laptop on every one of 2,000 test rows, and it classifies a flow in 295 microseconds, which is about 3,400 flows per second."

**Likely questions:**
- *What is the difference between 98.6 and 84.3?* "98.6 weights the test rows by how common each attack is in real traffic, where floods dominate and the model is nearly perfect. 84.3 gives every class equal weight, including the rare, hard ones. We report both so nobody can say we hid the hard classes."

---

## Slide 3: Introduction and motivation

**Say:**

"Why does this matter? Follow the flow at the top.

There are billions of IoT devices, and most of them ship with default passwords and never receive updates. Botnets recruit them. Mirai in 2016 took over hundreds of thousands of cameras and routers and used them to launch some of the largest DDoS attacks ever recorded. Once a device is recruited it sends floods, scans the network for more victims, and spoofs addresses. The current defence is cloud-based intrusion detection, and the problem with it is in the last box: the packets have to leave the device first. The device itself is blind.

So we have three things. The problem: IoT devices cannot run the deep models that server-side detection uses. They have kilobytes of RAM, no operating system and no GPU.

The idea: put a small but honest classifier on the same microcontroller class that IoT devices are actually built from. If an ESP32 can tell a flood from normal traffic in microseconds, then an IoT device can raise its own alarm.

The goal: train on a large public dataset, compress the model until it fits in flash, convert it to C, deploy it on a real board, and prove the chip gives the same answers as the laptop.

The numbers at the bottom show what we are working with. Five dollars, four megabytes of flash, 320 kilobytes of RAM, a 240 megahertz dual-core CPU and no GPU."

**Likely questions:**
- *Why ESP32 specifically?* "It is the chip inside a large share of real consumer IoT products, it has Wi-Fi built in, and it costs five dollars. If it works here, it works on the devices being attacked."

---

## Slide 4: Literature survey

**Say:**

"We looked at two kinds of prior work: datasets with detection results, and tools for running models on microcontrollers.

First, Neto and colleagues in 2023 published CICIoT2023, the dataset we use. It is real traffic from 105 IoT devices under 33 attacks, and the paper reports baseline classifiers: random forest, logistic regression, AdaBoost and a neural network. What it leaves open is that those baselines are evaluated on a laptop with a random split, and nothing is deployed on constrained hardware.

Second, Meidan and colleagues in 2018, N-BaIoT. They detected botnets on nine commercial IoT devices using deep autoencoders over 115 statistical features. The limitation is that the features are pre-extracted and the autoencoders are far too large for a microcontroller.

Third, Koroniotis and colleagues in 2019, Bot-IoT. A simulated testbed with DDoS, DoS, scanning and data theft, evaluated with SVM, RNN and LSTM. Again, simulated traffic and server-side models.

Fourth, emlearn by Nordby, 2019. This is a tool that converts scikit-learn tree ensembles into dependency-free C. It is a tool, not a study, so it does not tell you how accurate a compressed intrusion detection forest remains on a real chip.

Fifth, TensorFlow Lite Micro by David and colleagues, 2021. A framework for running small neural networks on microcontrollers. It targets neural networks, while for tabular flow features tree ensembles are usually smaller and faster.

The pattern is clear. Detection accuracy is studied on servers, and deployment tools are studied without an intrusion detection workload. Our project joins the two."

**Likely questions:**
- *Why not use TensorFlow Lite Micro with a neural network?* "We trained an MLP and a CNN as baselines. Both scored lower than the forest, and a forest compiles to pure if-else code with zero RAM, which no neural network can match."

---

## Slide 5: Research gaps

**Say:**

"Reading the survey side by side, four gaps appear.

Gap one, optimistic evaluation. Most published IoT IDS results use a random train-test split of the same captures. Network traffic contains many near-duplicate rows, so a random split lets almost identical rows land on both sides, and accuracy is inflated. Very few papers split by source file.

Gap two, no deployment. Models are trained and scored on laptops. Flash size, RAM use and latency on a real microcontroller are rarely reported, so nobody knows whether the published model could actually run where the attack happens.

Gap three, model size versus chip size. Deep detectors and large forests are hundreds of megabytes. A typical IoT microcontroller has a few megabytes of flash. The detector has to shrink by three orders of magnitude and still be useful.

Gap four, unverified conversion. When you convert a trained model to C, the way it votes changes and the way it rounds floating-point numbers changes. Without a row-by-row comparison against the original, the on-device accuracy is assumed, not shown.

Each of these gaps maps directly to one decision in our method: a file-grouped split, a real ESP32 deployment, feature and tree compression, and a 100 percent parity test."

**Likely questions:**
- *How do you know random splits inflate accuracy?* "We measured it. On our own data, the same forest scores higher on a random split than on the file-grouped split. Our own dedup step also removed 9.4 percent of the training rows as exact duplicates, which shows how much repetition there is."

---

## Slide 6: Proposed method

**Say:**

"Our method is a pipeline of seven numbered scripts, and each one writes its results to disk, so every number in this presentation can be traced back to a file.

Inventory: a script walks the 309 CSV files, counts rows per attack and records the class imbalance, which is 2,601 to one between the largest and smallest category.

Build dataset: this is the screenshot on the left, the real output of the build script. We deduplicate, which removes 9.4 percent of rows. We fix NaN and infinite values in the rate and variance columns. We drop two columns that are algebraic copies of others. Then the important step: we split 70-15-15 by source file, so every capture file goes entirely to train, validation or test. The leak check at the bottom confirms no file appears in two splits. That gives us 1.27 million training rows and 286 thousand test rows.

Baselines: we trained four model families on the same split, random forest, XGBoost, an MLP and a 1D CNN.

Compress: 37 features down to 25 by importance, 200 trees of unlimited depth down to 30 trees of depth 10, and 8 categories grouped into 5 classes. One detail that matters: we score every candidate with hard voting, where each tree casts one vote, because that is exactly how the C code will vote. That means the laptop number predicts the chip number.

Then compile to C, deploy to the board, and verify with a parity test and a live demo."

**Likely questions:**
- *Why drop two columns?* "'Tot size' is byte-for-byte identical to 'AVG', and 'Tot sum' equals AVG times Number. They carry no information."
- *Why 70-15-15?* "70 to train, 15 to validate the sweep choices, 15 held out and touched only for the final numbers."

---

## Slide 7: Architecture

**Say:**

"The architecture has two tiers.

The top row runs once, offline, on the laptop. The dataset goes through preprocessing and splitting. A random forest is trained with balanced class weights, so a rare class like brute force counts as much as benign traffic. The forest is compressed to 25 features, 30 trees, depth 10. Then emlearn turns it into a C header file.

The bottom row runs on the ESP32, for every single flow, in 295 microseconds. The chip receives 25 floating-point numbers on its serial port at 115200 baud. It parses them into a float array with the same function the laptop uses, so there is no rounding mismatch. It calls predict, where 30 trees each cast a vote and the majority wins. It replies with the class, the microseconds the prediction took, and an alert flag. And it drives the on-board LED: on for any attack class, off for benign.

Bottom left is why we chose the random forest. On the original 8 classes it scored a macro-F1 of 0.672, ahead of XGBoost at 0.635, the MLP at 0.597 and the CNN at 0.593. Just as important, a forest compiles to pure branch instructions and needs zero RAM.

Bottom right is the deployed model. Random forest with majority voting, 30 trees, depth 10, 26,376 nodes, 25 inputs, five classes, 240 kilobytes of flash and zero bytes of static RAM."

**Likely questions:**
- *What are the 25 features?* "Flow statistics over a window of packets: average, minimum and maximum packet size, standard deviation and variance, packet rate, inter-arrival time, time-to-live, header length, protocol type, the fraction of packets with each TCP flag, SYN and ACK counts, and whether the flow is TCP, UDP, ICMP, HTTP, HTTPS, SSH or DNS."
- *Why zero RAM?* "The trees are compiled as if-else statements on the input array. There are no weights to store at runtime."

---

## Slide 8: Technology used

**Say:**

"The software stack is small on purpose.

On the laptop: Python 3.13 with pandas, NumPy and scikit-learn for data handling and training. The dataset is CIC-IoT-2023. emlearn version 0.23 converts the scikit-learn forest to C. The Arduino IDE with the ESP32 core 3.3 provides the xtensa-gcc compiler and the esptool flasher. The board is an ESP32-WROOM-32 DevKit. And pyserial links the laptop to the board.

The screenshot on the left is the real generated header file. You can see the first tree: a function that takes the 25-float feature array and walks a chain of if statements on individual features, returning a class number at each leaf. The whole file is 52,945 lines, 2.9 megabytes of C source, with no malloc and no library calls.

The screenshot on the right is the real compiler output. The demo sketch uses 520 kilobytes, 39 percent of the application partition. Below it is the same sketch compiled with the forest stubbed out: 280 kilobytes. The difference, 240 kilobytes, is the model's actual flash footprint. That is how we measured it, not estimated it."

**Likely questions:**
- *2.9 megabytes of source but only 240 kilobytes in flash?* "Source text is verbose. Each node compiles to about 9 bytes of machine code."
- *Why Arduino and not ESP-IDF?* "The stock Arduino core was enough: one serial loop and one function call. Nothing in the project needed the lower-level framework."

---

## Slide 9: Output, part 1: classification results

**Say:**

"These are the results on the held-out test set, 286,197 rows from capture files the model never trained on, scored with hard voting exactly as the chip votes.

The three headline numbers: 98.6 percent accuracy on a real-traffic mix, 84.3 percent balanced accuracy, and macro-F1 of 0.82.

The confusion matrix on the left reads row by row: each row is the true class, each column is what the chip predicted. Flood and Mirai are essentially perfect at 100 percent. Benign is 82 percent, with 16 percent called Probe. Probe is 77 percent, with 19 percent called Benign. Spoofing is the hard class at 49 percent, because 40 percent of spoofing traffic looks like normal traffic in these flow statistics. Spoofing works by looking normal, so that is expected.

The per-class F1 chart tells the same story: Flood 0.999, Mirai 0.998, Probe 0.77, Benign 0.68, Spoofing 0.63.

The chart at the bottom right shows the effect of class grouping. With the original 8 classes, even the full 958-megabyte forest scored 77 percent balanced and 76.6 percent on real traffic, because it confused DDoS with DoS about a quarter of the time. Merging DDoS and DoS into Flood raised real-traffic accuracy to 98 percent. Merging Recon, Web and BruteForce into Probe raised balanced accuracy to 84.3. The model size is identical in all three cases; only the grouping changed."

**Likely questions:**
- *Is the model overfitting?* "No. Training accuracy is 88.8 percent against 84.3 on test, a four-point gap. A forest that memorises scores near 100 on training data."
- *Why merge DDoS and DoS?* "They produce the same flood signature. The only difference is how many sources the packets come from, and these flow features do not contain source addresses. A real alert would group them anyway."

---

## Slide 10: Output, part 2: on the chip

**Say:**

"Now the part that is actually running on hardware.

Left screenshot: the parity test. The laptop streams 2,000 held-out rows, 400 per class, over USB to the ESP32 on COM15. For each row the chip replies with its prediction and the time it took. We compare every reply with the prediction from the same C code compiled on the laptop. Result: 100 percent match, row for row, with zero communication errors. Board accuracy and laptop accuracy are identical at 81.35 percent on this balanced sample. Mean inference time 295 microseconds, median 299, maximum 541. Floods and Mirai are the fastest at around 228 microseconds because the trees reach a leaf early.

You also see 98.2 percent agreement with Python's scikit-learn. That gap is expected and explained: scikit-learn averages tree probabilities, while the chip counts one vote per tree. We verified this by emulating hard voting in Python, which matches the chip exactly.

Right screenshot: the live demo. The laptop replays random held-out flows in phases: normal traffic, a DDoS, normal again, a Mirai botnet, normal, then probing. The laptop only feeds flows. The chip classifies each one and lights its LED for attacks. In this run, 87 percent of flows got the exact class, 96 percent of attack flows were flagged, and Flood and Mirai were 35 out of 35. Roughly one in five benign flows triggered a false alarm, which matches the 16 percent on the confusion matrix. We did not cherry-pick rows; they are sampled at random."

**Likely questions:**
- *Why is demo accuracy 87 but the slide before says 98.6?* "The demo replays an equal mix of classes including the hard ones. Real traffic is mostly floods, which the chip gets right every time. Both numbers are honest; they weight the classes differently."
- *How is latency measured?* "On the chip itself, with micros() immediately before and after the single predict call."

---

## Slide 11: Conclusion and future work

**Say:**

"To conclude.

We took a random forest trained on CIC-IoT-2023 and compressed it 4,000 times, from 958 megabytes to 240 kilobytes, and it runs on a five-dollar ESP32.

On the chip it reaches 98.6 percent accuracy on a realistic traffic mix and 84.3 percent balanced accuracy, with Flood and Mirai detected almost perfectly.

The chip reproduces the laptop's prediction on 100 percent of 2,000 test rows and classifies a flow in 295 microseconds, about 3,400 flows per second, which is far more than a single IoT device ever sends.

And every number comes from a leak-free, file-grouped split, so it reflects traffic the model had never seen.

For future work, in order of impact. First, compute the 25 flow features on the ESP32 itself from live packets, so the device needs no laptop at all. The features are running statistics over a packet window, so this is feasible in constant memory. Second, add alerting over Wi-Fi, through MQTT or a small web page, and an OLED display, so detections are visible on the device. Third, measure energy per inference with an INA219 current sensor and compare the forest against a small neural network on the same board. Fourth, improve the separation of Spoofing from Benign with time-window features that the current flow statistics do not capture."

**Likely questions:**
- *What was the hardest part?* "Making the laptop number predict the chip number. Until we switched the sweep to hard voting and matched the float parsing, the chip disagreed with Python on a few percent of rows."

---

## Slide 12: References

**Say:**

"These are our references. One is the dataset paper. Two and three are the comparison datasets from the survey. Four and five are the two deployment tools. Six is Breiman's original random forest paper. Seven is the earlier CIC intrusion dataset whose feature-extraction approach CICIoT2023 follows. Eight is the ESP32 datasheet and Arduino core.

Thank you. I am happy to take questions, and the board is here if you would like to see the live demonstration."

---

## Running the live demo after questions

1. Plug in the board. Close the Arduino IDE so nothing else holds COM15.
2. Run, from the project folder:
   `python scripts/09_live_demo.py --port COM15 --led --delay 0.5`
3. Press Enter when prompted. Narrate: "The laptop is only feeding flows. Every verdict and the LED are decided on the chip."
4. When a red line appears during a normal phase: "That is one of the benign false alarms from the confusion matrix. We do not hide them."
5. If the port is busy: close the Serial Monitor and rerun. If no board is found: replug the USB cable and check the COM number in Device Manager.
6. Backup: `python scripts/09_live_demo.py --dry-run` runs the same forest on the laptop and says so on screen. Use it only if the board fails.
