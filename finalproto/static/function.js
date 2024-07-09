    let film;
    let currentRow = 0;
    let logdata;
    let isVideoLoaded = false;
    let isDataLoaded = false;
    let markers = [];
    let currentContent = "";
    let isSpeedEnabled = true;
    let currentSpeed = 1;
    let seekBarY = 550;
    let fx, fy, fw, fh;

    function preload() {
      loadTable("static/transcription.csv", "csv", "header",
        (table) => {
          logdata = table;
          isDataLoaded = true;
          console.log("CSV data loaded successfully");
          createMarkers();
        },
        (error) => console.error("Failed to load CSV:", error)
      );
    }

    function setup() {
      createCanvas(800, 600);
      background(220);

      playPauseButton = createButton('Play');
      playPauseButton.position(10, 40);
      playPauseButton.mousePressed(togglePlayback);

      speedToggleButton = createButton('Speed: ON');
      speedToggleButton.position(70, 40);
      speedToggleButton.mousePressed(toggleSpeed);
      updateSpeedButtonAppearance();

      film = createVideo(["url_for{{'static', filename="video_filename") }}"], vidLoad);
      film.hide();

      seekSlider = createSlider(0, 100, 0, 0.1);
      seekSlider.position(10, seekBarY);
      seekSlider.style('width', `${width - 20}px`);
      seekSlider.style('opacity', '0');
      seekSlider.input(userSeeking);
      seekSlider.changed(userSeeked);

      noLoop();
    }

    function createMarkers() {
      for (let i = 0; i < logdata.getRowCount(); i++) {
        let content = logdata.getString(i, 2);
        if (content.includes("うわ") || content.includes("よし")) {
          markers.push({
            time: logdata.getNum(i, 0),
            type: content.includes("うわ") ? "うわ" : "よし"
          });
        }
      }
    }

    function vidLoad() {
      console.log('Video loaded successfully');
      isVideoLoaded = true;
      resizeVideo();
      playPauseButton.html('Play');
      seekSlider.attribute('max', film.duration());
    }

    function resizeVideo() {
      let margin = 150;
      let maxWidth = 800;
      let maxHeight = 600 - margin;
      let videoRatio = film.width / film.height;
      let screenRatio = maxWidth / maxHeight;

      if (videoRatio > screenRatio) {
        fw = maxWidth;
        fh = fw / videoRatio;
      } else {
        fh = maxHeight;
        fw = fh * videoRatio;
      }

      fx = (width - fw) / 2;
      fy = (height - margin - fh) / 2;
    }

    function togglePlayback() {
      if (!isVideoLoaded) {
        console.log('Video is not loaded yet. Please wait for the video to load.');
        return;
      }

      if (film.elt.paused) {
        startPlayback();
      } else {
        pausePlayback();
      }
    }

    function startPlayback() {
      film.play();
      playPauseButton.html('Pause');
      loop();
    }

    function pausePlayback() {
      if (isVideoLoaded && !film.elt.paused) {
        film.pause();
        playPauseButton.html('Play');
        noLoop();
      }
    }

    function toggleSpeed() {
      isSpeedEnabled = !isSpeedEnabled;
      updateSpeedButtonAppearance();
      updateSpeed();
    }

    function updateSpeedButtonAppearance() {
      if (isSpeedEnabled) {
        speedToggleButton.html('Speed: ON');
        speedToggleButton.style('background-color', '#4CAF50');
        speedToggleButton.style('color', 'white');
      } else {
        speedToggleButton.html('Speed: OFF');
        speedToggleButton.style('background-color', '#f44336');
        speedToggleButton.style('color', 'white');
      }
    }

    function updateSpeed() {
      if (isSpeedEnabled && !currentContent.includes("うわ") && !currentContent.includes("よし")) {
        currentSpeed = 2;
      } else {
        currentSpeed = 1;
      }
      film.speed(currentSpeed);
    }

    function userSeeking() {
      updateSeekPosition();
    }

    function userSeeked() {
      updateSeekPosition();
      if (!film.elt.paused) {
        loop();
      }
    }

    function updateSeekPosition() {
      let seekTime = map(seekSlider.value(), 0, 100, 0, film.duration());
      film.time(seekTime);
    }

    function draw() {
      if (!isVideoLoaded || !isDataLoaded) return;

      let currentTime = film.time();
      let bgColor = getColorFromContent(currentContent);
      background(bgColor);

      image(film, fx, fy, fw, fh);

      drawMarkers();

      if (logdata && currentRow < logdata.getRowCount()) {
        let startTime = logdata.getNum(currentRow, 0);
        let endTime = logdata.getNum(currentRow, 1);

        if (currentTime >= startTime && currentTime < endTime) {
          currentContent = logdata.getString(currentRow, 2);
          fill(255);
          noStroke();
          rect(10, height - 50, width - 20, 30);
          fill(0);
          textSize(16);
          text(`Current content: ${currentContent}`, 20, height - 30);

          updateSpeed();
        } else if (currentTime >= endTime) {
          currentRow++;
          currentContent = "";
          updateSpeed();
        }
      } else {
        currentContent = "";
        updateSpeed();
      }

      fill(0);
      textSize(16);
      text(`Current time: ${currentTime.toFixed(2)}s`, 20, height - 10);
      text(`Current speed: ${currentSpeed}x`, 200, height - 10);
    }

    function drawMarkers() {
      for (let marker of markers) {
        let markerX = map(marker.time, 0, film.duration(), 10, width - 10);
        let markerColor = marker.type === "うわ" ? color(0, 0, 255) : color(255, 165, 0);
        fill(markerColor);
        ellipse(markerX, height - 70, 10, 10);
      }
    }

    function getColorFromContent(content) {
      if (content.includes("うわ")) {
        return color(0, 0, 255);
      } else if (content.includes("よし")) {
        return color(255, 165, 0);
      } else {
        return color(220);
      }
