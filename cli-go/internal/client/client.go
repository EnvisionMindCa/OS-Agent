package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
}

func New(baseURL string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
}

type SessionInfo struct {
	Sessions []string `json:"sessions"`
}

func (c *Client) ListSessions(ctx context.Context, user string) ([]string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/sessions/%s", c.baseURL, user), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("list sessions failed: %s", resp.Status)
	}
	var data SessionInfo
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}
	return data.Sessions, nil
}

type ChatRequest struct {
	User    string `json:"user"`
	Session string `json:"session"`
	Prompt  string `json:"prompt"`
}

func (c *Client) ChatStream(ctx context.Context, user, session, prompt string) (io.ReadCloser, error) {
	body, err := json.Marshal(ChatRequest{User: user, Session: session, Prompt: prompt})
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/chat/stream", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("chat failed: %s - %s", resp.Status, string(b))
	}
	return resp.Body, nil
}

type UploadResp struct {
	Path string `json:"path"`
}

func (c *Client) UploadDocument(ctx context.Context, user, session, path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()

	buf := &bytes.Buffer{}
	writer := multipart.NewWriter(buf)
	_ = writer.WriteField("user", user)
	_ = writer.WriteField("session", session)
	fw, err := writer.CreateFormFile("file", filepath.Base(path))
	if err != nil {
		return "", err
	}
	if _, err = io.Copy(fw, file); err != nil {
		return "", err
	}
	writer.Close()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/upload", buf)
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("upload failed: %s - %s", resp.Status, string(b))
	}
	var out UploadResp
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	return out.Path, nil
}

type DirEntry struct {
	Name  string `json:"name"`
	IsDir bool   `json:"is_dir"`
}

type DirList struct {
	Entries []DirEntry `json:"entries"`
}

func (c *Client) ListDir(ctx context.Context, user, path string) ([]DirEntry, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/vm/%s/list?path=%s", c.baseURL, user, path), nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("list dir failed: %s", resp.Status)
	}
	var out DirList
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}
	return out.Entries, nil
}

type FileContent struct {
	Content string `json:"content"`
}

func (c *Client) ReadFile(ctx context.Context, user, path string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		fmt.Sprintf("%s/vm/%s/file?path=%s", c.baseURL, user, path), nil)
	if err != nil {
		return "", err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("read file failed: %s", resp.Status)
	}
	var out FileContent
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	return out.Content, nil
}

func (c *Client) WriteFile(ctx context.Context, user, path, content string) error {
	data, _ := json.Marshal(map[string]string{"path": path, "content": content})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost,
		fmt.Sprintf("%s/vm/%s/file", c.baseURL, user), bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("write file failed: %s - %s", resp.Status, string(b))
	}
	return nil
}

func (c *Client) DeleteFile(ctx context.Context, user, path string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete,
		fmt.Sprintf("%s/vm/%s/file?path=%s", c.baseURL, user, path), nil)
	if err != nil {
		return err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("delete file failed: %s - %s", resp.Status, string(b))
	}
	return nil
}
