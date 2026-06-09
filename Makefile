include wg21/Makefile

.PHONY: examples
examples:
	$(MAKE) -j $(shell nproc) -f examples/Makefile

clean: clean-examples

.PHONY: clean-examples
clean-examples:
	$(MAKE) -f examples/Makefile clean
