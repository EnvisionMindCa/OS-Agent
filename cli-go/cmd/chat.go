package cmd

import (
	"bufio"
	"fmt"
	"os"
	"strconv"

	"github.com/fatih/color"
	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newChatCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "chat",
		Short: "Start an interactive chat session",
		RunE:  runChat,
	}
	return cmd
}

func runChat(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()
	c := client.New(server)

	sessions, err := c.ListSessions(ctx, user)
	if err != nil {
		return err
	}

	session := "default"
	if len(sessions) > 0 {
		fmt.Println("Existing sessions:")
		for i, s := range sessions {
			fmt.Printf("  %d. %s\n", i+1, s)
		}
		fmt.Printf("Select session number or enter new name [%d]: ", len(sessions))
		var choice string
		fmt.Scanln(&choice)
		if n, err := strconv.Atoi(choice); err == nil && n >= 1 && n <= len(sessions) {
			session = sessions[n-1]
		} else if choice != "" {
			session = choice
		}
	}

	cyan := color.New(color.FgCyan).SprintFunc()
	green := color.New(color.FgGreen).SprintFunc()
	yellow := color.New(color.FgYellow).SprintFunc()

	fmt.Printf("Chatting as %s in session '%s'\n", green(user), session)

	scanner := bufio.NewScanner(os.Stdin)
	for {
		fmt.Printf("%s> ", cyan("You"))
		if !scanner.Scan() {
			break
		}
		line := scanner.Text()
		if line == "exit" || line == "quit" {
			break
		}
		stream, err := c.ChatStream(ctx, user, session, line)
		if err != nil {
			fmt.Println("error:", err)
			continue
		}
		r := bufio.NewReader(stream)
		for {
			part, err := r.ReadString('\n')
			if len(part) > 0 {
				fmt.Print(yellow(part))
			}
			if err != nil {
				break
			}
		}
		stream.Close()
	}
	return nil
}
