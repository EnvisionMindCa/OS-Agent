package cmd

import (
	"context"
	"fmt"

	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newUploadCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "upload [file]",
		Short: "Upload a document to the VM",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx := context.Background()
			c := client.New(server)
			path, err := c.UploadDocument(ctx, user, "default", args[0])
			if err != nil {
				return err
			}
			fmt.Println("Uploaded to", path)
			return nil
		},
	}
}
