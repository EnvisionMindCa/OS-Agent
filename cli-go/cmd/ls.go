package cmd

import (
	"context"
	"fmt"

	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newLsCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "ls [path]",
		Short: "List directory contents in the VM",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			path := "/data"
			if len(args) == 1 {
				path = args[0]
			}
			c := client.New(server)
			entries, err := c.ListDir(context.Background(), user, path)
			if err != nil {
				return err
			}
			for _, e := range entries {
				if e.IsDir {
					fmt.Println(e.Name + "/")
				} else {
					fmt.Println(e.Name)
				}
			}
			return nil
		},
	}
}
