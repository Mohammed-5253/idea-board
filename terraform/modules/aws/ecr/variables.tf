variable "name" {
  description = "Repository prefix, e.g. idea-board → idea-board/backend."
  type        = string
}

variable "images" {
  type    = list(string)
  default = ["backend", "frontend"]
}
