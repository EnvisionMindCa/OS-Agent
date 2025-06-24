import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js'; // Assuming hls.js is installed
import '../styles/VMStreamViewer.css';

interface StreamInfo {
  url: string;
  type: string; // e.g., "HLS", "RTSP_placeholder", "MP4"
}

const VMStreamViewer: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [streamInfo, setStreamInfo] = useState<StreamInfo | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch the stream URL from the backend
    fetch('http://localhost:8000/api/stream_url')
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to fetch stream URL: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then((data: StreamInfo) => {
        setStreamInfo(data);
        setIsLoading(false);
      })
      .catch(err => {
        console.error("Error fetching stream info:", err);
        setError(`Could not load stream info: ${err.message}. Ensure backend is running and provides a valid stream URL.`);
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    if (streamInfo && videoRef.current) {
      const videoElement = videoRef.current;
      setError(null); // Clear previous errors

      if (streamInfo.type.toUpperCase() === 'HLS' || (streamInfo.url.includes('.m3u8') && Hls.isSupported())) {
        console.log("Attempting to play HLS stream:", streamInfo.url);
        const hls = new Hls();
        hls.loadSource(streamInfo.url);
        hls.attachMedia(videoElement);
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          videoElement.play().catch(playError => {
            console.error("Error trying to play HLS stream:", playError);
            setError(`Video play failed. User interaction might be required, or stream format is unsupported directly. ${playError.message}`);
          });
        });
        hls.on(Hls.Events.ERROR, (event, data) => {
          if (data.fatal) {
            switch (data.type) {
              case Hls.ErrorTypes.NETWORK_ERROR:
                console.error('HLS Network error:', data);
                setError(`Network error loading stream. Check URL and network. Details: ${data.details}`);
                break;
              case Hls.ErrorTypes.MEDIA_ERROR:
                console.error('HLS Media error:', data);
                setError(`Media error with stream. Details: ${data.details}`);
                hls.recoverMediaError();
                break;
              default:
                console.error('HLS Unrecoverable error:', data);
                setError(`Error loading HLS stream. Details: ${data.details}`);
                hls.destroy();
                break;
            }
          }
        });
        return () => { // Cleanup on component unmount or streamInfo change
          hls.destroy();
        };
      } else if (streamInfo.type.toUpperCase() === 'RTSP_PLACEHOLDER') {
        console.warn("RTSP stream detected. Native browser playback is not supported.");
        setError("Received RTSP stream URL. RTSP is not directly playable in browsers. Server-side transcoding to HLS or DASH is required.");
      } else if (videoElement.canPlayType(streamInfo.type) || streamInfo.url.endsWith('.mp4')) { // Basic MP4 or other directly supported format
        console.log("Attempting to play direct video URL:", streamInfo.url);
        videoElement.src = streamInfo.url;
        videoElement.play().catch(playError => {
          console.error("Error trying to play direct video stream:", playError);
          setError(`Video play failed. ${playError.message}`);
        });
      } else {
        console.warn(`Unsupported stream type: ${streamInfo.type} or URL: ${streamInfo.url}`);
        setError(`Unsupported stream type '${streamInfo.type}' or URL. Cannot play directly in the browser.`);
      }
    }
  }, [streamInfo]); // Re-run when streamInfo changes

  return (
    <div className="vm-stream-container styled-container">
      <h2>VM Stream</h2>
      <div className="video-player-wrapper">
        {isLoading && <div className="loading-indicator"><p>Loading stream info...</p></div>}
        {!isLoading && error && <div className="stream-error-message"><p>{error}</p></div>}
        {!isLoading && !error && !streamInfo && <div className="stream-error-message"><p>No stream information available.</p></div>}
        {!isLoading && streamInfo && (
          <video ref={videoRef} controls muted playsInline className="video-element">
            Your browser does not support the video tag or the stream format.
          </video>
        )}
        {streamInfo && streamInfo.type.toUpperCase() === 'RTSP_PLACEHOLDER' && (
          <div className="stream-info-message">
            <p><strong>Note:</strong> The backend provided an RTSP stream URL (`{streamInfo.url}`). RTSP requires server-side conversion (e.g., to HLS) for browser playback. This player is configured for HLS.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default VMStreamViewer;
